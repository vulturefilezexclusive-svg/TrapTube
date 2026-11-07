import Foundation
import AuthenticationServices
import Combine
import CryptoKit
import Security
import UIKit

@MainActor
final class GoogleYouTubeAuth: NSObject, ObservableObject, ASWebAuthenticationPresentationContextProviding {
    static let shared = GoogleYouTubeAuth()
    static let clientID = "521019296185-7k6g1bvb2sb7nojhci6m8mhq4sk4fmaf.apps.googleusercontent.com"
    static let callbackScheme = "com.googleusercontent.apps.521019296185-7k6g1bvb2sb7nojhci6m8mhq4sk4fmaf"
    static let redirectURI = callbackScheme + ":/oauth2redirect"
    static let youtubeScope = "https://www.googleapis.com/auth/youtube.readonly"

    @Published private(set) var isSignedIn = false
    @Published private(set) var displayName: String?
    @Published private(set) var email: String?
    @Published private(set) var lastError: String?

    private var session: ASWebAuthenticationSession?
    private var accessToken: String?
    private var accessTokenExpiry = Date.distantPast
    private let refreshTokenKey = "traptube.google.refresh-token"

    override init() {
        super.init()
        Task { await restoreSession() }
    }

    func signIn() async {
        lastError = nil
        do {
            let verifier = Self.randomURLSafeString(count: 64)
            let challenge = Self.sha256(verifier)
            let state = Self.randomURLSafeString(count: 24)
            var components = URLComponents(string: "https://accounts.google.com/o/oauth2/v2/auth")!
            components.queryItems = [
                URLQueryItem(name: "client_id", value: Self.clientID),
                URLQueryItem(name: "redirect_uri", value: Self.redirectURI),
                URLQueryItem(name: "response_type", value: "code"),
                URLQueryItem(name: "scope", value: "openid email profile \(Self.youtubeScope)"),
                URLQueryItem(name: "code_challenge", value: challenge),
                URLQueryItem(name: "code_challenge_method", value: "S256"),
                URLQueryItem(name: "state", value: state),
                URLQueryItem(name: "access_type", value: "offline"),
                URLQueryItem(name: "include_granted_scopes", value: "true"),
                URLQueryItem(name: "prompt", value: "consent")
            ]
            guard let authURL = components.url else { throw AuthError.invalidURL }
            let code = try await authorizationCode(for: authURL, expectedState: state)
            try await exchangeAuthorizationCode(code, verifier: verifier)
            try await loadProfile()
            isSignedIn = true
        } catch {
            lastError = error.localizedDescription
        }
    }

    func signOut() {
        accessToken = nil
        accessTokenExpiry = .distantPast
        displayName = nil
        email = nil
        isSignedIn = false
        lastError = nil
        KeychainTokenStore.delete(key: refreshTokenKey)
    }

    func authorizedGET(_ url: URL) async throws -> Data {
        let token = try await validAccessToken()
        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw AuthError.apiFailure(String(data: data, encoding: .utf8) ?? "YouTube API request failed.")
        }
        return data
    }

    private func restoreSession() async {
        guard KeychainTokenStore.read(key: refreshTokenKey) != nil else { return }
        do {
            _ = try await validAccessToken()
            try await loadProfile()
            isSignedIn = true
        } catch {
            lastError = error.localizedDescription
            isSignedIn = false
        }
    }

    private func validAccessToken() async throws -> String {
        if let accessToken, accessTokenExpiry.timeIntervalSinceNow > 60 { return accessToken }
        guard let refresh = KeychainTokenStore.read(key: refreshTokenKey) else { throw AuthError.notSignedIn }
        var request = URLRequest(url: URL(string: "https://oauth2.googleapis.com/token")!)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        request.httpBody = Self.formEncoded([
            "client_id": Self.clientID,
            "grant_type": "refresh_token",
            "refresh_token": refresh
        ])
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw AuthError.tokenFailure(String(data: data, encoding: .utf8) ?? "Google token refresh failed.")
        }
        let token = try JSONDecoder().decode(TokenResponse.self, from: data)
        accessToken = token.access_token
        accessTokenExpiry = Date().addingTimeInterval(TimeInterval(token.expires_in))
        return token.access_token
    }

    private func authorizationCode(for url: URL, expectedState: String) async throws -> String {
        try await withCheckedThrowingContinuation { continuation in
            let authSession = ASWebAuthenticationSession(url: url, callbackURLScheme: Self.callbackScheme) { callback, error in
                if let error { continuation.resume(throwing: error); return }
                guard let callback,
                      let parts = URLComponents(url: callback, resolvingAgainstBaseURL: false),
                      let returnedState = parts.queryItems?.first(where: { $0.name == "state" })?.value,
                      returnedState == expectedState else {
                    continuation.resume(throwing: AuthError.invalidCallback); return
                }
                if let oauthError = parts.queryItems?.first(where: { $0.name == "error" })?.value {
                    continuation.resume(throwing: AuthError.oauth(oauthError)); return
                }
                guard let code = parts.queryItems?.first(where: { $0.name == "code" })?.value else {
                    continuation.resume(throwing: AuthError.missingCode); return
                }
                continuation.resume(returning: code)
            }
            authSession.presentationContextProvider = self
            authSession.prefersEphemeralWebBrowserSession = false
            self.session = authSession
            if !authSession.start() {
                self.session = nil
                continuation.resume(throwing: AuthError.browserUnavailable)
            }
        }
    }

    private func exchangeAuthorizationCode(_ code: String, verifier: String) async throws {
        var request = URLRequest(url: URL(string: "https://oauth2.googleapis.com/token")!)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        request.httpBody = Self.formEncoded([
            "client_id": Self.clientID,
            "code": code,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": Self.redirectURI
        ])
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw AuthError.tokenFailure(String(data: data, encoding: .utf8) ?? "Google authorization exchange failed.")
        }
        let token = try JSONDecoder().decode(TokenResponse.self, from: data)
        accessToken = token.access_token
        accessTokenExpiry = Date().addingTimeInterval(TimeInterval(token.expires_in))
        if let refresh = token.refresh_token { KeychainTokenStore.save(refresh, key: refreshTokenKey) }
    }

    private func loadProfile() async throws {
        let url = URL(string: "https://www.googleapis.com/oauth2/v2/userinfo")!
        let data = try await authorizedGET(url)
        let profile = try JSONDecoder().decode(GoogleProfile.self, from: data)
        displayName = profile.name
        email = profile.email
    }

    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap(\.windows)
            .first(where: \.isKeyWindow) ?? UIWindow()
    }

    private static func randomURLSafeString(count: Int) -> String {
        var bytes = [UInt8](repeating: 0, count: count)
        _ = SecRandomCopyBytes(kSecRandomDefault, count, &bytes)
        return Data(bytes).base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }

    private static func sha256(_ value: String) -> String {
        let digest = SHA256.hash(data: Data(value.utf8))
        return Data(digest).base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }

    private static func formEncoded(_ values: [String: String]) -> Data {
        let allowed = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._* ")
        let body = values.sorted { $0.key < $1.key }.map { key, value in
            let k = key.addingPercentEncoding(withAllowedCharacters: allowed) ?? key
            let v = value.addingPercentEncoding(withAllowedCharacters: allowed) ?? value
            return "\(k.replacingOccurrences(of: " ", with: "+"))=\(v.replacingOccurrences(of: " ", with: "+"))"
        }.joined(separator: "&")
        return Data(body.utf8)
    }

    private struct TokenResponse: Decodable {
        let access_token: String
        let expires_in: Int
        let refresh_token: String?
    }
    private struct GoogleProfile: Decodable { let name: String?; let email: String? }

    private enum AuthError: LocalizedError {
        case invalidURL, invalidCallback, missingCode, browserUnavailable, notSignedIn
        case oauth(String), tokenFailure(String), apiFailure(String)
        var errorDescription: String? {
            switch self {
            case .invalidURL: return "Google sign-in URL could not be created."
            case .invalidCallback: return "Google returned an invalid sign-in callback."
            case .missingCode: return "Google did not return an authorization code."
            case .browserUnavailable: return "The secure sign-in browser could not be started."
            case .notSignedIn: return "Connect a Google account first."
            case .oauth(let message), .tokenFailure(let message), .apiFailure(let message): return message
            }
        }
    }
}

private enum KeychainTokenStore {
    static func save(_ value: String, key: String) {
        let data = Data(value.utf8)
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrAccount as String: key]
        SecItemDelete(query as CFDictionary)
        var insert = query
        insert[kSecValueData as String] = data
        insert[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(insert as CFDictionary, nil)
    }
    static func read(key: String) -> String? {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrAccount as String: key, kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
    static func delete(key: String) {
        SecItemDelete([kSecClass as String: kSecClassGenericPassword, kSecAttrAccount as String: key] as CFDictionary)
    }
}
