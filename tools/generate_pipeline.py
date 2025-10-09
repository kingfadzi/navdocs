#!/usr/bin/env python3
"""
Dynamic Pipeline Generator
Generates GitLab CI child pipeline based on which BOM files changed
"""

import sys
import os
import subprocess
import yaml
from pathlib import Path


def get_changed_boms():
    """Detect which BOM files have changed."""
    changed_boms = []

    # In CI, use git diff to find changed files
    commit_before = os.environ.get('CI_COMMIT_BEFORE_SHA', '')

    # Skip if this is the first commit (all zeros) or not set
    if not commit_before or commit_before == '0' * 40:
        print("First commit or local run - checking both BOMs")
        changed_boms = ['baseline', 'functional']
    else:
        try:
            result = subprocess.run(
                ['git', 'diff', '--name-only', f'{commit_before}...HEAD'],
                capture_output=True,
                text=True,
                check=True
            )
            changed_files = result.stdout.strip().split('\n')

            if 'boms/baseline.yaml' in changed_files:
                changed_boms.append('baseline')
            if 'boms/functional.yaml' in changed_files:
                changed_boms.append('functional')

        except subprocess.CalledProcessError as e:
            print(f"Git diff failed: {e}")
            # Fallback: check both BOMs
            changed_boms = ['baseline', 'functional']

    return changed_boms


def get_env_from_branch():
    """Map branch to environment configuration."""
    branch = os.environ.get('CI_COMMIT_BRANCH', 'feature/test')

    if branch == 'main':
        return {
            'env': 'prod',
            'env_upper': 'PROD',
            'needs_review': True,
            'artifact_expiry': '1 year'
        }
    elif branch == 'develop':
        return {
            'env': 'staging',
            'env_upper': 'STAGING',
            'needs_review': False,
            'artifact_expiry': '90 days'
        }
    else:  # feature/* branches
        return {
            'env': 'test',
            'env_upper': 'TEST',
            'needs_review': False,
            'artifact_expiry': '30 days'
        }


def generate_pipeline():
    """Generate the complete child pipeline."""
    changed_boms = get_changed_boms()

    if not changed_boms:
        print("No BOM changes detected")
        return {'stages': ['.pre']}  # Minimal no-op pipeline

    print(f"Generating pipeline for: {', '.join(changed_boms)}")

    env_cfg = get_env_from_branch()
    env = env_cfg['env']

    # Build stages (maintains baseline → functional sequence)
    stages = []

    if 'baseline' in changed_boms:
        if env_cfg['needs_review']:
            stages.append('review_baseline')
        stages.extend(['extract_baseline', 'import_baseline', 'archive_baseline'])

    if 'functional' in changed_boms:
        if env_cfg['needs_review']:
            stages.append('review_functional')
        stages.extend(['extract_functional', 'import_functional', 'archive_functional'])

    stages.append('.post')  # For rollback jobs

    # Start building pipeline
    pipeline = {
        'stages': stages,
        'include': [{'local': 'templates/job-templates.yml'}]
    }

    # Generate jobs for each BOM type
    for bom_type in changed_boms:
        bom_upper = bom_type.upper()

        # REVIEW (prod only)
        if env_cfg['needs_review']:
            pipeline[f'review:{env}:{bom_type}'] = {
                'extends': f'.review_{bom_type}_template',
                'stage': f'review_{bom_type}',
                'variables': {'DEPLOY_ENV': env_cfg['env_upper']},
                'when': 'manual',
                'allow_failure': False
            }

        # EXTRACT
        extract_job = {
            'extends': f'.extract_{bom_type}_template',
            'stage': f'extract_{bom_type}',
            'variables': {'DEPLOY_ENV': env_cfg['env_upper']},
            'artifacts': {
                'paths': [
                    f'bundles/{bom_type}-*.xml',
                    f'bundles/deployment-metadata-{bom_type}.yaml'
                ],
                'expire_in': '7 days'
            }
        }

        # Add dependency on review if needed
        if env_cfg['needs_review']:
            extract_job['dependencies'] = [f'review:{env}:{bom_type}']

        pipeline[f'extract:{env}:{bom_type}'] = extract_job

        # IMPORT
        import_job = {
            'extends': f'.import_{bom_type}_template',
            'stage': f'import_{bom_type}',
            'variables': {'DEPLOY_ENV': env_cfg['env_upper']},
            'dependencies': [f'extract:{env}:{bom_type}']
        }

        # Prod imports kept for 1 year
        if env == 'prod':
            import_job['artifacts'] = {'expire_in': '1 year'}

        pipeline[f'import:{env}:{bom_type}'] = import_job

        # ARCHIVE
        pipeline[f'archive:{env}:{bom_type}'] = {
            'extends': f'.archive_{bom_type}_template',
            'stage': f'archive_{bom_type}',
            'variables': {'DEPLOY_ENV': env_cfg['env_upper']},
            'dependencies': [f'import:{env}:{bom_type}'],
            'artifacts': {
                'paths': [
                    f'archives/{bom_type}-*.zip',
                    f'evidence/{bom_type}-*.zip',
                    f'ROLLBACK_MANIFEST_{bom_upper}.yaml'
                ],
                'expire_in': env_cfg['artifact_expiry']
            }
        }

        # ROLLBACK
        pipeline[f'rollback:{env}:{bom_type}'] = {
            'extends': f'.rollback_{bom_type}_template',
            'stage': '.post',
            'variables': {'DEPLOY_ENV': env_cfg['env_upper']},
            'needs': [
                {'job': f'extract:{env}:{bom_type}', 'artifacts': True, 'optional': True}
            ],
            'when': 'manual'
        }

    return pipeline


def main():
    """Main entry point."""
    pipeline = generate_pipeline()

    # Write to file
    output_file = 'generated-pipeline.yml'
    with open(output_file, 'w') as f:
        yaml.dump(pipeline, f, default_flow_style=False, sort_keys=False)

    print(f"\n{'='*60}")
    print(f"Generated pipeline saved to: {output_file}")
    print(f"{'='*60}")
    print("\nPipeline contents:")
    print("-" * 60)
    with open(output_file, 'r') as f:
        print(f.read())
    print("-" * 60)


if __name__ == '__main__':
    main()
