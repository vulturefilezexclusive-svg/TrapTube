from pathlib import Path
import sys

services = Path(sys.argv[1])
project = Path(sys.argv[2])
legacy_name = "Type" + "TypeService.swift"
replacement_name = "MediaDownloadService.swift"

legacy_files = list(services.rglob(legacy_name))
for legacy in legacy_files:
    legacy.unlink()

project_text = project.read_text()
project_text = project_text.replace(legacy_name, replacement_name)
project.write_text(project_text)
