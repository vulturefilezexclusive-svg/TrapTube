import Foundation
import Security

struct TypeTypeInstance: Decodable {
    let name: String?
    let version: String?
    let apiVersion: Int?
    let guestAllowed: Bool?
    let supportedServices: [Int]?
}

struct TypeTypeVideo: Decodable, Identifiable {
    let id: String
    let title: String
    let url: String
    let thumbnailUrl: String
    let uploaderName: String
    let uploaderUrl: String?
    let duration: Int64
    let viewCount: Int64?
    let streamType: String?
    let isLive: Bool?
    let shortDescription: String?

    var displayDuration: String {
        let total = max(0, Int(duration))
        return String(format: "%d:%02d", total / 60, total % 60)
    }

    var watchParameter: String {
        guard let components = URLComponents(string: url) else { return id }
        if let value = components.queryItems?.first(where: { $0.name == "v" })?.value, !value.isEmpty { return value }
        let last = components.path.split(separator: "/").last.map(String.init) ?? id
        return last
    }
}

struct TypeTypeSearchPage: Decodable {
    let items: [TypeTypeVideo]
    let nextpage: String?
    let searchSuggestion: String?
    let isCorrectedSearch: Bool?
}

struct TypeTypeService {
    static let baseAddress = URL(string: "https://watch.typetype.video")!
    private static let tokenAccount = "typetype.accessToken"
    private var token: String? { TokenStore.read(Self.tokenAccount) }

    enum ServiceError: LocalizedError {
        case invalidAddress, guestNotAllowed, missingToken, sessionExpired, badResponse(Int, String)
        var errorDescription: String? {
            switch self {
            case .invalidAddress: return "The TypeType server address is invalid."
            case .guestNotAllowed: return "This TypeType instance does not allow guest access. Sign-in is required."
            case .missingToken: return "TypeType did not return an access token."
            case .sessionExpired: return "The TypeType guest session expired and could not be renewed."
            case let .badResponse(code, message): return "TypeType returned HTTP \(code): \(message)"
            }
        }
    }

    func checkHealth() async throws -> String {
        let instance = try await connect()
        return "Connected to \(instance.name ?? "TypeType") · v\(instance.version ?? "unknown") · API \(instance.apiVersion ?? 0)"
    }

    func connect() async throws -> TypeTypeInstance {
        let instance: TypeTypeInstance = try await request(path: "/api/instance", authenticated: false)
        if token == nil || token?.isEmpty == true {
            guard instance.guestAllowed == true else { throw ServiceError.guestNotAllowed }
            try await fetchGuestToken()
        }
        return instance
    }

    /// Guest access tokens are short-lived (the server issues one-hour access tokens), so a stored
    /// token must be treated as renewable rather than permanent.
    private func fetchGuestToken() async throws {
        struct GuestResponse: Decodable { let token: String?; let accessToken: String? }
        do {
            let response: GuestResponse = try await request(path: "/api/auth/guest", method: "POST", body: Data("{}".utf8), authenticated: false, allowReauth: false)
            guard let value = response.token ?? response.accessToken, !value.isEmpty else { throw ServiceError.missingToken }
            TokenStore.write(value, account: Self.tokenAccount)
        } catch ServiceError.badResponse(401, _), ServiceError.badResponse(403, _) {
            throw ServiceError.guestNotAllowed
        }
    }

    func trending(serviceID: Int = 0) async throws -> [TypeTypeVideo] {
        try await ensureToken()
        return try await request(path: "/api/trending", query: [URLQueryItem(name: "service", value: String(serviceID))], authenticated: true)
    }

    func search(query: String, serviceID: Int = 0, nextPage: String? = nil) async throws -> TypeTypeSearchPage {
        try await ensureToken()
        var items = [URLQueryItem(name: "q", value: query), URLQueryItem(name: "service", value: String(serviceID))]
        if let nextPage, !nextPage.isEmpty { items.append(URLQueryItem(name: "nextpage", value: nextPage)) }
        return try await request(path: "/api/search", query: items, authenticated: true)
    }

    func watchURL(for video: TypeTypeVideo) -> URL? {
        var components = URLComponents(url: Self.baseAddress, resolvingAgainstBaseURL: false)
        components?.path = "/watch"
        components?.queryItems = [URLQueryItem(name: "v", value: video.watchParameter)]
        return components?.url
    }

    private func ensureToken() async throws {
        if token?.isEmpty != false { _ = try await connect() }
    }

    private func request<T: Decodable>(path: String, method: String = "GET", query: [URLQueryItem] = [], body: Data? = nil, authenticated: Bool = true, allowReauth: Bool = true) async throws -> T {
        var components = URLComponents(url: Self.baseAddress, resolvingAgainstBaseURL: false)!
        components.path = path
        components.queryItems = query.isEmpty ? nil : query
        guard let url = components.url else { throw ServiceError.invalidAddress }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 30
        request.httpBody = body
        if body != nil { request.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        if authenticated, let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw ServiceError.badResponse(-1, "No HTTP response") }
        if http.statusCode == 401, authenticated, allowReauth {
            // Expired or revoked token: discard it, obtain a fresh guest token once, and retry once.
            TokenStore.delete(Self.tokenAccount)
            do { try await fetchGuestToken() } catch { throw ServiceError.sessionExpired }
            return try await self.request(path: path, method: method, query: query, body: body, authenticated: authenticated, allowReauth: false)
        }
        guard (200..<300).contains(http.statusCode) else {
            let detail = String(data: data.prefix(400), encoding: .utf8) ?? "Request failed"
            throw ServiceError.badResponse(http.statusCode, detail)
        }
        guard !data.isEmpty else { throw ServiceError.badResponse(http.statusCode, "The server returned an empty response.") }
        do { return try JSONDecoder().decode(T.self, from: data) }
        catch { throw ServiceError.badResponse(200, "The server response did not match the expected TypeType data format.") }
    }
}

/// Keychain-backed storage for the TypeType access token (migrates the legacy UserDefaults value).
enum TokenStore {
    private static let service = "com.greatmusic.traptube.typetype"

    static func read(_ account: String) -> String? {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                    kSecAttrAccount as String: account, kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var item: CFTypeRef?
        if SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess, let data = item as? Data,
           let value = String(data: data, encoding: .utf8), !value.isEmpty { return value }
        // Legacy location: move once, then forget it.
        if let legacy = UserDefaults.standard.string(forKey: account), !legacy.isEmpty {
            write(legacy, account: account)
            UserDefaults.standard.removeObject(forKey: account)
            return legacy
        }
        return nil
    }

    static func write(_ value: String, account: String) {
        delete(account)
        let attributes: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                         kSecAttrAccount as String: account, kSecValueData as String: Data(value.utf8),
                                         kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock]
        SecItemAdd(attributes as CFDictionary, nil)
    }

    static func delete(_ account: String) {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: account]
        SecItemDelete(query as CFDictionary)
        UserDefaults.standard.removeObject(forKey: account)
    }
}
