#!/usr/bin/env python3
"""
Generate Python client from IRI OpenAPI specification.

This script can be used standalone or imported into CI/CD pipelines.

Usage examples::

    # Generate the v1 client (default package name: amsc_iri)
    python generate.py --api-version 1 --package-version 1.3.0

    # Generate the v2 client as a separate package
    python generate.py --api-version 2 --package-name amsc_iri_v2 \\
        --project-name amsc-iri-v2 --package-version 2.0.1

    # Both can coexist -- output dirs default to the package name:
    #   ./amsc_iri/      (v1, import amsc_iri)
    #   ./amsc_iri_v2/   (v2, import amsc_iri_v2)

    # Use explicit URL (backward compatible)
    python generate.py --api-url https://custom-host/api/v2/openapi.json

Credit: https://gitlab.com/amsc2/infrastructure-and-services/amsc-interfaces/amsc-api-python
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError


DEFAULT_API_BASE = "https://iri-dev.ppg.es.net"
DEFAULT_API_VERSION = 2
DEFAULT_API_URL = f"{DEFAULT_API_BASE}/api/v{DEFAULT_API_VERSION}/openapi.json"
CONFIG_FILE = "config.yaml"
DEFAULT_PACKAGE_NAME = "amsc_iri"


def check_api_accessibility(api_url: str) -> bool:
    """Check if the API is accessible."""
    try:
        with urlopen(api_url, timeout=5) as response:
            return response.status == 200
    except (URLError, Exception):
        return False


def check_tool_installed() -> bool:
    """Check if openapi-python-client is installed."""
    return shutil.which("openapi-generator") is not None


def generate_client(
    api_url: str,
    config_file: str,
    output_dir: str,
    package_name: str,
    package_version: str = None,
    project_name: str = None,
) -> bool:
    """
    Generate the Python client.
    
    Args:
        api_url:         OpenAPI spec URL to generate from.
        config_file:     Path to openapi-generator config file.
        output_dir:      Output directory for generated code.
        package_name:    Python package name (e.g. ``amsc_iri``,
                         ``amsc_iri_v2``).  Controls the import name.
        package_version: If set, passed to openapi-generator via
                         ``--additional-properties=packageVersion=X.Y.Z``
                         so the generated ``pyproject.toml`` gets the
                         correct version string instead of the default
                         ``1.0.0``.
        project_name:    pip project name for pyproject.toml (e.g.
                         ``amsc-iri-v2``).  If not given, defaults to
                         *package_name* with underscores replaced by
                         hyphens.

    Returns:
        True if generation was successful, False otherwise.
    """
    script_dir = Path(__file__).parent
    config_path = script_dir / config_file
    output_path = script_dir / output_dir
    
    # Remove existing generated client
    if output_path.exists():
        print(f"🗑️  Removing existing generated client at {output_path}")
        shutil.rmtree(output_path)
    
    # Build command
    cmd = [
        "openapi-generator",
        "generate",
        "-i", api_url,
        "-g", "python",
        "-o", str(output_path),
        "--package-name", str(package_name),
    ]

    # Build additional-properties for pyproject.toml metadata
    additional = []
    if package_version:
        additional.append(f"packageVersion={package_version}")
    resolved_project = project_name or package_name.replace("_", "-")
    additional.append(f"projectName={resolved_project}")
    if additional:
        cmd.extend([
            "--additional-properties",
            ",".join(additional),
        ])
    
    print(f"⚙️  Generating Python client...")
    print(f"   Command: {' '.join(cmd)}")
    print()
    
    try:
        result = subprocess.run(
            cmd,
            cwd=script_dir,
            check=True,
            capture_output=False,
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Generation failed with exit code {e.returncode}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate Python client from IRI OpenAPI specification"
    )
    parser.add_argument(
        "--api-version",
        type=int,
        default=None,
        help=(
            f"IRI API version to generate from (e.g. 1 or 2). "
            f"Constructs the spec URL as "
            f"{DEFAULT_API_BASE}/api/v{{N}}/openapi.json. "
            f"Overrides --api-url when provided. "
            f"(default: {DEFAULT_API_VERSION})"
        ),
    )
    parser.add_argument(
        "--api-url",
        default=None,
        help=(
            f"OpenAPI JSON URL. Ignored when --api-version is given. "
            f"(default: {DEFAULT_API_URL})"
        ),
    )
    parser.add_argument(
        "--package-version",
        default=None,
        help=(
            "Version string for the generated pyproject.toml "
            "(e.g. '2.1.0'). Without this flag the openapi-generator "
            "defaults to '1.0.0'."
        ),
    )
    parser.add_argument(
        "--config",
        default=CONFIG_FILE,
        help=f"Config file path (default: {CONFIG_FILE})",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Output directory. Defaults to the value of --package-name "
            f"(e.g. '{DEFAULT_PACKAGE_NAME}' or 'amsc_iri_v2')."
        ),
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Skip API accessibility check",
    )
    parser.add_argument(
        "--package-name",
        default=DEFAULT_PACKAGE_NAME,
        help=(
            "Python import package name. Controls the generated module "
            f"directory name (default: {DEFAULT_PACKAGE_NAME})."
        ),
    )
    parser.add_argument(
        "--project-name",
        default=None,
        help=(
            "pip project name for pyproject.toml (e.g. 'amsc-iri-v2'). "
            "Defaults to --package-name with underscores replaced by "
            "hyphens."
        ),
    )
    
    args = parser.parse_args()

    # Resolve the API URL: --api-version takes precedence over --api-url
    if args.api_version is not None:
        api_url = f"{DEFAULT_API_BASE}/api/v{args.api_version}/openapi.json"
    elif args.api_url is not None:
        api_url = args.api_url
    else:
        api_url = DEFAULT_API_URL

    # Resolve output directory: default to the package name so that
    # generating v1 and v2 from the same checkout does not collide.
    output_dir = args.output or args.package_name

    # Resolve pip project name
    project_name = args.project_name or args.package_name.replace("_", "-")

    print("=" * 60)
    print(" IRI Python Client Generator")
    print("=" * 60)
    print()
    print(f"API URL:         {api_url}")
    if args.api_version is not None:
        print(f"API Version:     v{args.api_version}")
    print(f"Config:          {args.config}")
    print(f"Output:          {output_dir}")
    print(f"Package name:    {args.package_name}")
    print(f"Project name:    {project_name}")
    if args.package_version:
        print(f"Package version: {args.package_version}")
    else:
        print(f"Package version: (openapi-generator default)")
    print()
    
    # Check if tool is installed
    if not check_tool_installed():
        print("❌ openapi-generator is not installed")
        print()
        print("To install (macOS), run:")
        print("  brew install openapi-generator")
        print()
        sys.exit(1)
    
    # Check API accessibility
    if not args.skip_check:
        print("🔍 Checking API accessibility...")
        if check_api_accessibility(api_url):
            print("✓ API is accessible")
            print()
        else:
            print(f"❌ Cannot access API at {api_url}")
            print()
            print("Make sure the API server is running:")
            print("  make")
            print()
            print("Or use --skip-check to bypass this check")
            print()
            sys.exit(1)
    
    # Generate client
    if generate_client(
        api_url,
        args.config,
        output_dir,
        args.package_name,
        package_version=args.package_version,
        project_name=project_name,
    ):
        print()
        print("=" * 60)
        print("  Client generated successfully!")
        print("=" * 60)
        print()
        print(f"Location: {output_dir}")
        if args.package_version:
            print(f"Package version: {args.package_version}")
        print()
        print("To install the client:")
        print(f"  cd {output_dir}")
        print("  pip install -e .")
        print()
        sys.exit(0)
    else:
        print()
        print("❌ Client generation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

