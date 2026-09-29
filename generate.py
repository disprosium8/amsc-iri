#!/usr/bin/env python3
"""
Generate Python client from IRI OpenAPI specification.

This script can be used standalone or imported into CI/CD pipelines.

Usage examples::

    # Generate from v2 spec with package version 2.1.0
    python generate.py --api-version 2 --package-version 2.1.0

    # Generate from v1 spec (for comparison or testing)
    python generate.py --api-version 1 --package-version 1.3.0

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
OUTPUT_DIR = "generated"


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
) -> bool:
    """
    Generate the Python client.
    
    Args:
        api_url:         OpenAPI spec URL to generate from.
        config_file:     Path to openapi-generator config file.
        output_dir:      Output directory for generated code.
        package_name:    Python package name (e.g. ``amsc_iri``).
        package_version: If set, passed to openapi-generator via
                         ``--additional-properties=packageVersion=X.Y.Z``
                         so the generated ``pyproject.toml`` gets the
                         correct version string instead of the default
                         ``1.0.0``.

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

    # Set the package version in the generated pyproject.toml
    if package_version:
        cmd.extend([
            "--additional-properties",
            f"packageVersion={package_version}",
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
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})",
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Skip API accessibility check",
    )
    parser.add_argument(
        "--package-name",
        default="amsc_iri",
        help="Package name (default: amsc_iri)",
    )
    
    args = parser.parse_args()

    # Resolve the API URL: --api-version takes precedence over --api-url
    if args.api_version is not None:
        api_url = f"{DEFAULT_API_BASE}/api/v{args.api_version}/openapi.json"
    elif args.api_url is not None:
        api_url = args.api_url
    else:
        api_url = DEFAULT_API_URL

    print("=" * 60)
    print(" IRI Python Client Generator")
    print("=" * 60)
    print()
    print(f"API URL:         {api_url}")
    if args.api_version is not None:
        print(f"API Version:     v{args.api_version}")
    print(f"Config:          {args.config}")
    print(f"Output:          {args.output}")
    print(f"Package name:    {args.package_name}")
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
        args.output,
        args.package_name,
        package_version=args.package_version,
    ):
        print()
        print("=" * 60)
        print("  ✅ Client generated successfully!")
        print("=" * 60)
        print()
        print(f"Location: {args.output}")
        if args.package_version:
            print(f"Package version: {args.package_version}")
        print()
        print("To install the client:")
        print(f"  cd {args.output}")
        print("  pip install -e .")
        print()
        print("To run tests:")
        print("  python tests/test_workflow_simple.py")
        print()
        sys.exit(0)
    else:
        print()
        print("❌ Client generation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

