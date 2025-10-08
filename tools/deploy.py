#!/usr/bin/env python3
"""
PPM Deployment Orchestrator
Extracts and imports PPM entities across environments
"""

import yaml
import subprocess
import sys
import os
from pathlib import Path
import glob
import zipfile
import shutil
from datetime import datetime
import nexus_client
from validate_bom import validate_bom


def load_yaml(file_path):
    """Load YAML file and return contents."""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


def validate_bom_before_deploy(bom_file):
    """
    Run BOM validation before deployment (mirrors CI validate stage).
    Exits with error code 1 if validation fails.
    """
    print("=" * 60)
    print("STAGE 1: VALIDATION")
    print("=" * 60)
    print(f"Validating: {bom_file}")
    print()

    is_valid, errors = validate_bom(bom_file)

    if not is_valid:
        print("  INVALID")
        for error in errors:
            print(f"    - {error}")
        print()
        print("=" * 60)
        print("VALIDATION FAILED")
        print("=" * 60)
        print("Fix validation errors before deploying")
        sys.exit(1)

    print("  VALID")
    print()


def get_flag_string(profile_name):
    """
    Get compiled flag string from profile.
    Calls flag_compiler.py and returns the 25-character Y/N string.
    """
    script_dir = Path(__file__).parent
    compiler = script_dir / "flag_compiler.py"

    result = subprocess.run(
        ['python3', str(compiler), profile_name],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()


def run_extract(script_path, url, entity_id, reference_code=None):
    """
    Run kMigratorExtract.sh to extract an entity.
    Returns the path to the created bundle file.
    """
    # Get credentials from environment variables
    username = os.environ['PPM_USERNAME']
    password = os.environ['PPM_PASSWORD']

    # Build command
    cmd = [
        'sh', script_path,
        '-username', username,
        '-password', password,
        '-url', url,
        '-action', 'Bundle',
        '-entityId', str(entity_id)
    ]

    # Add reference code if specified (for specific entities)
    if reference_code:
        cmd.extend(['-referenceCode', reference_code])

    # Print what we're doing
    print(f"Extracting entity {entity_id}" + (f" ({reference_code})" if reference_code else " (ALL)") + f" from {url}")
    print(f"Command: {' '.join(cmd)}")
    print()

    # Run extraction
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    print(result.stdout)

    # Find the bundle file that was created
    # Look for "Bundle saved to: " in output
    for line in result.stdout.split('\n'):
        if 'Bundle saved to:' in line:
            return line.split('Bundle saved to:')[1].strip()

    # Fallback: find most recent bundle for this entity
    pattern = f"./bundles/KMIGRATOR_EXTRACT_{entity_id}_*.xml"
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    return files[0] if files else None


def run_import(script_path, url, bundle_file, flags, i18n, refdata):
    """
    Run kMigratorImport.sh to import a bundle.
    """
    # Get credentials from environment variables
    username = os.environ['PPM_USERNAME']
    password = os.environ['PPM_PASSWORD']

    # Build command
    cmd = [
        'sh', script_path,
        '-username', username,
        '-password', password,
        '-url', url,
        '-action', 'import',
        '-filename', bundle_file,
        '-i18n', i18n,
        '-refdata', refdata,
        '-flags', flags
    ]

    # Print what we're doing
    print(f"Importing {bundle_file} to {url}")
    print(f"Command: {' '.join(cmd)}")
    print()

    # Run import
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    print(result.stdout)


def create_evidence_package(bom_file, archive_path, config):
    """
    Create evidence package for compliance/audit.
    Bundles: BOM, archive manifest, deployment metadata
    Returns path to the created evidence package.
    """
    root = Path(__file__).parent.parent
    evidence_dir = root / "evidence"
    evidence_dir.mkdir(exist_ok=True)

    # Load BOM metadata
    bom = load_yaml(bom_file)
    version = bom.get('version', 'unknown')
    change_request = bom.get('change_request', 'baseline')
    target_server = bom.get('target_server', 'unknown')

    # Create evidence filename
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    evidence_name = f"{change_request}-{target_server}-{timestamp}-evidence.zip"
    evidence_path = evidence_dir / evidence_name

    print(f"Creating evidence package: {evidence_name}")

    with zipfile.ZipFile(evidence_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # BOM snapshot
        zipf.write(bom_file, arcname="bom-deployed.yaml")
        print(f"  Added: bom-deployed.yaml")

        # Copy manifest from deployment archive
        if Path(archive_path).exists():
            with zipfile.ZipFile(archive_path, 'r') as archive_zip:
                manifest_content = archive_zip.read("manifest.yaml")
                zipf.writestr("archive-manifest.yaml", manifest_content)
                print(f"  Added: archive-manifest.yaml")

        # Metadata with CI/CD context
        metadata = {
            'bom_file': str(bom_file),
            'archive_path': str(archive_path),
            'deployment_timestamp': datetime.now().isoformat(),
            'ci_commit_sha': os.environ.get('CI_COMMIT_SHA', 'local'),
            'ci_commit_branch': os.environ.get('CI_COMMIT_BRANCH', 'local'),
            'ci_pipeline_id': os.environ.get('CI_PIPELINE_ID', 'local'),
            'ci_pipeline_url': os.environ.get('CI_PIPELINE_URL', 'local'),
            'ci_job_url': os.environ.get('CI_JOB_URL', 'local'),
            'deployed_by': os.environ.get('GITLAB_USER_LOGIN', os.environ.get('USER', 'unknown'))
        }
        zipf.writestr("metadata.yaml", yaml.dump(metadata, default_flow_style=False))
        print(f"  Added: metadata.yaml")

    print(f"Evidence package created: {evidence_path}")
    return evidence_path


def archive_deployment(bundles, bom_file, flags, config):
    """
    Create a ZIP archive with bundles + BOM + flags for rollback.
    Returns path to the created ZIP file.
    """
    # Get archive directory from config
    root = Path(__file__).parent.parent
    archive_dir = root / config['deployment']['archive_dir']
    archive_dir.mkdir(exist_ok=True)

    # Load BOM to get version and change request
    bom = load_yaml(bom_file)
    version = bom.get('version', 'unknown')
    change_request = bom.get('change_request', 'baseline')

    # Create archive filename: CR-{ticket}-v{version}-bundles.zip
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    archive_name = f"{change_request}-v{version}-{timestamp}-bundles.zip"
    archive_path = archive_dir / archive_name

    print(f"Creating deployment archive: {archive_name}")

    # Create ZIP file
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add all bundle files
        for bundle in bundles:
            bundle_path = Path(bundle)
            zipf.write(bundle, arcname=f"bundles/{bundle_path.name}")
            print(f"  Added: {bundle_path.name}")

        # Add BOM file
        bom_path = Path(bom_file)
        zipf.write(bom_file, arcname="bom.yaml")
        print(f"  Added: bom.yaml")

        # Add flags.txt
        flags_content = flags
        zipf.writestr("flags.txt", flags_content)
        print(f"  Added: flags.txt")

        # Add manifest with metadata
        manifest = {
            'version': version,
            'change_request': change_request,
            'archived_at': datetime.now().isoformat(),
            'bundles': [Path(b).name for b in bundles],
            'flags': flags
        }
        zipf.writestr("manifest.yaml", yaml.dump(manifest))
        print(f"  Added: manifest.yaml")

    print(f"Archive created: {archive_path}")
    return archive_path


def push_to_nexus(archive_path, bom_file, config):
    """
    Mock Nexus upload: Copy archive to nexus-storage directory.
    Returns the Nexus artifact URL.
    """
    # Load BOM
    bom = load_yaml(bom_file)

    # Get Nexus config
    nexus_config = config['nexus']
    repository = nexus_config['repository']
    subfolder = nexus_config.get('subfolder', '')

    # Build artifact path in Nexus
    archive_name = Path(archive_path).name
    artifact_path = f"{subfolder}/{archive_name}" if subfolder else archive_name

    print(f"Pushing to mock Nexus repository '{repository}'...")

    # Upload to mock Nexus (just file copy)
    artifact_url = nexus_client.upload_artifact(
        None,  # nexus_url not used in mock
        repository,
        artifact_path,
        archive_path
    )
    print(f"Artifact URL: {artifact_url}")
    return artifact_url


def baseline_repave(bom_file):
    """
    Deploy ALL baseline entities.
    Entity list comes from profile.
    """
    # Validate BOM first (mirrors CI pipeline)
    validate_bom_before_deploy(bom_file)

    # Get paths
    root = Path(__file__).parent.parent

    # Load BOM
    bom = load_yaml(bom_file)
    profile_name = bom['profile']

    # Runtime check: Profile must match deployment type
    if 'baseline' not in profile_name.lower():
        print("=" * 60)
        print("ERROR: Profile Mismatch")
        print("=" * 60)
        print(f"baseline-repave command requires a baseline profile")
        print(f"Found profile: {profile_name}")
        print()
        print(f"Use: python3 tools/deploy.py functional-release --bom {bom_file}")
        print("=" * 60)
        sys.exit(1)

    print("=" * 60)
    print("STAGE 2: BASELINE REPAVE")
    print("=" * 60)
    print(f"BOM: {bom_file}")
    print()

    source_server = bom['source_server']
    target_server = bom['target_server']

    print(f"Source: {source_server}")
    print(f"Target: {target_server}")
    print(f"Profile: {profile_name}")
    print()

    # Load config and profile
    config = load_yaml(root / "config" / "deployment-config.yaml")
    profile = load_yaml(root / "profiles" / f"{profile_name}.yaml")

    source_url = config['servers'][source_server]['url']
    target_url = config['servers'][target_server]['url']
    extract_script = config['kmigrator']['extract_script']
    import_script = config['kmigrator']['import_script']

    # Get flags
    print(f"Compiling flags from {profile_name} profile...")
    flags = get_flag_string(profile_name)
    print(f"Flags: {flags}")
    print()

    # Extract all entities from profile
    print(f"Extracting {len(profile['entities'])} entity types...")
    print()

    bundles = []
    for entity in profile['entities']:
        bundle = run_extract(extract_script, source_url, entity['id'])
        bundles.append(bundle)
        print()

    # Import all bundles
    print(f"Importing {len(bundles)} bundles...")
    print()

    for bundle in bundles:
        run_import(import_script, target_url, bundle, flags, 'none', 'nochange')
        print()

    # Archive and push to Nexus
    print("=" * 60)
    print("ARCHIVING DEPLOYMENT")
    print("=" * 60)
    print()

    archive_path = archive_deployment(bundles, bom_file, flags, config)
    push_to_nexus(archive_path, bom_file, config)
    print()

    # Create evidence package
    print("=" * 60)
    print("CREATING EVIDENCE PACKAGE")
    print("=" * 60)
    print()
    create_evidence_package(bom_file, archive_path, config)
    print()

    # Cleanup
    print("Cleaning up temporary files...")
    for bundle in bundles:
        os.remove(bundle)
        print(f"Deleted: {bundle}")
    print()

    print("=" * 60)
    print(f"COMPLETE: {len(bundles)} entity types deployed")
    print("=" * 60)


def functional_release(bom_file):
    """
    Deploy SPECIFIC functional entities.
    Entity list comes from BOM.
    """
    # Validate BOM first (mirrors CI pipeline)
    validate_bom_before_deploy(bom_file)

    # Get paths
    root = Path(__file__).parent.parent

    # Load BOM
    bom = load_yaml(bom_file)
    profile_name = bom['profile']

    # Runtime check: Profile must match deployment type
    if 'functional' not in profile_name.lower():
        print("=" * 60)
        print("ERROR: Profile Mismatch")
        print("=" * 60)
        print(f"functional-release command requires a functional profile")
        print(f"Found profile: {profile_name}")
        print()
        print(f"Use: python3 tools/deploy.py baseline-repave --bom {bom_file}")
        print("=" * 60)
        sys.exit(1)

    print("=" * 60)
    print("STAGE 2: FUNCTIONAL RELEASE")
    print("=" * 60)
    print(f"BOM: {bom_file}")
    print()

    source_server = bom['source_server']
    target_server = bom['target_server']

    print(f"Source: {source_server}")
    print(f"Target: {target_server}")
    print(f"Profile: {profile_name}")
    print()

    # Load config
    config = load_yaml(root / "config" / "deployment-config.yaml")

    source_url = config['servers'][source_server]['url']
    target_url = config['servers'][target_server]['url']
    extract_script = config['kmigrator']['extract_script']
    import_script = config['kmigrator']['import_script']

    # Get flags
    print(f"Compiling flags from {profile_name} profile...")
    flags = get_flag_string(profile_name)
    print(f"Flags: {flags}")
    print()

    # Extract specific entities from BOM
    print(f"Extracting {len(bom['entities'])} entities...")
    print()

    bundles = []
    for entity in bom['entities']:
        bundle = run_extract(
            extract_script,
            source_url,
            entity['entity_id'],
            entity['reference_code']
        )
        bundles.append(bundle)
        print()

    # Import all bundles
    print(f"Importing {len(bundles)} bundles...")
    print()

    for bundle in bundles:
        run_import(import_script, target_url, bundle, flags, 'charset', 'nochange')
        print()

    # Archive and push to Nexus
    print("=" * 60)
    print("ARCHIVING DEPLOYMENT")
    print("=" * 60)
    print()

    archive_path = archive_deployment(bundles, bom_file, flags, config)
    push_to_nexus(archive_path, bom_file, config)
    print()

    # Create evidence package
    print("=" * 60)
    print("CREATING EVIDENCE PACKAGE")
    print("=" * 60)
    print()
    create_evidence_package(bom_file, archive_path, config)
    print()

    # Cleanup
    print("Cleaning up temporary files...")
    for bundle in bundles:
        os.remove(bundle)
        print(f"Deleted: {bundle}")
    print()

    print("=" * 60)
    print(f"COMPLETE: {len(bundles)} entities deployed")
    print("=" * 60)


def rollback(bom_file):
    """
    Rollback deployment by downloading and redeploying previous artifact.
    Uses rollback_artifact reference from BOM.
    """
    # Validate BOM first (mirrors CI pipeline)
    validate_bom_before_deploy(bom_file)

    print("=" * 60)
    print("STAGE 2: ROLLBACK DEPLOYMENT")
    print("=" * 60)
    print(f"BOM: {bom_file}")
    print()

    # Get paths
    root = Path(__file__).parent.parent

    # Load BOM
    bom = load_yaml(bom_file)
    rollback_artifact = bom.get('rollback_artifact')

    if not rollback_artifact:
        print("Error: No rollback_artifact specified in BOM")
        sys.exit(1)

    target_server = bom['target_server']

    print(f"Target: {target_server}")
    print(f"Rollback artifact: {rollback_artifact}")
    print()

    # Load config
    config = load_yaml(root / "config" / "deployment-config.yaml")
    target_url = config['servers'][target_server]['url']
    import_script = config['kmigrator']['import_script']

    # Download artifact from Nexus
    print("Downloading rollback artifact from Nexus...")
    archive_dir = root / config['deployment']['archive_dir']
    archive_dir.mkdir(exist_ok=True)
    archive_path = archive_dir / "rollback-temp.zip"

    nexus_client.download_artifact(rollback_artifact, archive_path)
    print()

    # Extract archive
    print("Extracting rollback archive...")
    extract_dir = archive_dir / "rollback-extract"
    extract_dir.mkdir(exist_ok=True)

    with zipfile.ZipFile(archive_path, 'r') as zipf:
        zipf.extractall(extract_dir)
        print(f"Extracted to: {extract_dir}")
    print()

    # Read flags from archive
    flags_file = extract_dir / "flags.txt"
    with open(flags_file, 'r') as f:
        flags = f.read().strip()

    print(f"Using original deployment flags: {flags}")
    print()

    # Find all bundles in archive
    bundle_dir = extract_dir / "bundles"
    bundles = list(bundle_dir.glob("*.xml"))

    print(f"Found {len(bundles)} bundles to import")
    print()

    # Import all bundles
    for bundle in bundles:
        run_import(import_script, target_url, str(bundle), flags, 'charset', 'nochange')
        print()

    # Cleanup
    print("Cleaning up temporary files...")
    shutil.rmtree(extract_dir)
    os.remove(archive_path)
    print()

    print("=" * 60)
    print(f"ROLLBACK COMPLETE: {len(bundles)} entities restored")
    print("=" * 60)


def main():
    """Main entry point - parse command line and run deployment."""

    # Check command line arguments
    if len(sys.argv) < 4:
        print("Usage:")
        print("  deploy.py baseline-repave --bom BOM_FILE")
        print("  deploy.py functional-release --bom BOM_FILE")
        print("  deploy.py rollback --bom BOM_FILE")
        print()
        print("Examples:")
        print("  deploy.py baseline-repave --bom boms/baseline-prod-to-test.yaml")
        print("  deploy.py functional-release --bom boms/release-example.yaml")
        print("  deploy.py rollback --bom boms/release-example.yaml")
        print()
        print("Note: For CI/CD pipelines, use baseline-repave or functional-release")
        print("      The script handles all stages: extract → import → archive")
        sys.exit(1)

    # Parse arguments
    deployment_type = sys.argv[1]
    bom_file = sys.argv[3]  # Expects --bom at position 2

    # Run the appropriate deployment
    if deployment_type == 'baseline-repave':
        baseline_repave(bom_file)
    elif deployment_type == 'functional-release':
        functional_release(bom_file)
    elif deployment_type == 'rollback':
        rollback(bom_file)
    else:
        print(f"Error: Unknown deployment type: {deployment_type}")
        sys.exit(1)


if __name__ == '__main__':
    main()
