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

project.save
puts "Linked FFmpegKit product ffmpegkit at #{revision} to #{target.name}."
