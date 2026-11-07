#!/usr/bin/env ruby
require "xcodeproj"

project_path = ARGV.fetch(0)
project = Xcodeproj::Project.open(project_path)
target = project.targets.find { |candidate| candidate.name == "TrapTube" }
abort "TrapTube target not found in #{project_path}" unless target

repository = "https://github.com/jaywcjlove/ffmpeg-kit.git"
revision = "0bd85df8f9693061f6f979414662baaf876a3e20"

package = project.root_object.package_references.find do |reference|
  reference.respond_to?(:repositoryURL) && reference.repositoryURL == repository
end

unless package
  package = project.new(Xcodeproj::Project::Object::XCRemoteSwiftPackageReference)
  package.repositoryURL = repository
  package.requirement = { "kind" => "revision", "revision" => revision }
  project.root_object.package_references << package
end

dependency = target.package_product_dependencies.find do |item|
  item.product_name == "ffmpegkit" && item.package == package
end

unless dependency
  dependency = project.new(Xcodeproj::Project::Object::XCSwiftPackageProductDependency)
  dependency.package = package
  dependency.product_name = "ffmpegkit"
  target.package_product_dependencies << dependency

  frameworks_phase = target.frameworks_build_phase
  unless frameworks_phase
    frameworks_phase = project.new(Xcodeproj::Project::Object::PBXFrameworksBuildPhase)
    target.build_phases << frameworks_phase
  end

  build_file = project.new(Xcodeproj::Project::Object::PBXBuildFile)
  build_file.product_ref = dependency
  frameworks_phase.files << build_file
end

# The Google auth overlay is copied into the project tree by the workflow.
# Add it explicitly because this Xcode project uses explicit source-file references.
if auth_source = ARGV[1]
  abort "GoogleYouTubeAuth.swift is missing at #{auth_source}" unless File.file?(auth_source)
  auth_path = File.expand_path(auth_source)
  auth_ref = project.files.find { |file| File.expand_path(file.real_path.to_s) == auth_path rescue false }
  unless auth_ref
    auth_ref = project.new(Xcodeproj::Project::Object::PBXFileReference)
    auth_ref.path = auth_path
    auth_ref.source_tree = "<absolute>"
    auth_ref.last_known_file_type = "sourcecode.swift"
    auth_ref.name = "GoogleYouTubeAuth.swift"
    project.main_group.children << auth_ref
  end
  unless target.source_build_phase.files_references.include?(auth_ref)
    target.source_build_phase.add_file_reference(auth_ref)
  end
  puts "Added GoogleYouTubeAuth.swift to #{target.name} compile sources."
end

# Native Metal-backed Demucs engine. Model weights are downloaded on first use.
demucs_repository = "https://github.com/SplitFireAI/demucs-swift.git"
demucs_package = project.root_object.package_references.find do |reference|
  reference.respond_to?(:repositoryURL) && reference.repositoryURL == demucs_repository
end
unless demucs_package
  demucs_package = project.new(Xcodeproj::Project::Object::XCRemoteSwiftPackageReference)
  demucs_package.repositoryURL = demucs_repository
  demucs_package.requirement = { "kind" => "upToNextMajorVersion", "minimumVersion" => "0.1.0" }
  project.root_object.package_references << demucs_package
end
demucs_dependency = target.package_product_dependencies.find do |item|
  item.product_name == "Demucs" && item.package == demucs_package
end
unless demucs_dependency
  demucs_dependency = project.new(Xcodeproj::Project::Object::XCSwiftPackageProductDependency)
  demucs_dependency.package = demucs_package
  demucs_dependency.product_name = "Demucs"
  target.package_product_dependencies << demucs_dependency
  frameworks_phase = target.frameworks_build_phase
  unless frameworks_phase
    frameworks_phase = project.new(Xcodeproj::Project::Object::PBXFrameworksBuildPhase)
    target.build_phases << frameworks_phase
  end
  build_file = project.new(Xcodeproj::Project::Object::PBXBuildFile)
  build_file.product_ref = demucs_dependency
  frameworks_phase.files << build_file
end
puts "Linked Demucs product Demucs from #{demucs_repository} (>= 0.1.0) to #{target.name}."

project.save
puts "Linked FFmpegKit product ffmpegkit at #{revision} to #{target.name}."
