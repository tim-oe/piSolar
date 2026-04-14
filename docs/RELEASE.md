# Release and Deployment

## Creating a Release

### Release Process

1. **Update version in `pyproject.toml`:**
   ```toml
   [project]
   version = "1.0.0"
   ```

2. **Commit the version change:**
   ```bash
   git add pyproject.toml
   git commit -m "Bump version to 1.0.0"
   ```

3. **Create and push tag:**
   ```bash
   git tag v1.0.0
   git push origin main
   git push origin v1.0.0
   ```

GitHub Actions automatically builds and publishes the release.

### Automated (Recommended)

GitHub Actions automatically builds and publishes releases when you push a version tag:

```bash
git tag v1.0.0
git push origin v1.0.0
```

This triggers `.github/workflows/release.yml` which:
1. Builds the deployment package (`pisolar-1.0.0.tar.gz`)
2. Creates a GitHub Release
3. Uploads the package as a release asset

### Documentation References

- [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
- [GitHub Actions Workflows](https://docs.github.com/en/actions/using-workflows/about-workflows)
- [GitHub Actions - Publishing Packages](https://docs.github.com/en/actions/publishing-packages/about-packaging-with-github-actions)
- [Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)

### Manual Build

If you need to build locally without creating a release:

```bash
poetry run build-release
```

Version is read from `pyproject.toml`. Package is created at: `build/release/pisolar-<version>.tar.gz`

## Installing on Raspberry Pi

Download and extract the release (always extracts to `pisolar/` directory):

```bash
wget https://github.com/YOUR_USERNAME/piSolar/releases/download/v1.0.0/pisolar-1.0.0.tar.gz
tar -xzf pisolar-1.0.0.tar.gz
cd pisolar
```

Run the installation script:

```bash
sudo ./install.sh
```

This installs to `/opt/pisolar` and sets up:
- Virtual environment with dependencies
- Configuration files in `/etc/pisolar`
- Systemd service

After installation:
- Configure the application: See [CONFIGURATION.md](CONFIGURATION.md)
- Manage the service: See [SYSTEMD.md](SYSTEMD.md)

## Upgrading

Stop the service, extract new version, and reinstall:

```bash
tar -xzf pisolar-1.1.0.tar.gz
cd pisolar
sudo ./install.sh
```

## Package Contents

The release package (~19KB) contains only runtime files:
- `pisolar/` - Python application
- `config/` - Configuration templates
- `systemd/` - Service definition
- `requirements.txt` - Dependencies
- `install.sh` - Installation script

Development files (tests, docs, Poetry) are excluded via `.deployignore`.

## GitHub Actions Workflows

Two workflows automate the release process:

### `.github/workflows/release.yml`
- **Trigger:** Push version tag (e.g., `v1.0.0`)
- **Actions:**
  - Reads version from `pyproject.toml`
  - Builds release package
  - Creates GitHub Release
  - Uploads tarball as asset
  - Warns if tag version doesn't match `pyproject.toml`

### `.github/workflows/build-test.yml`
- **Trigger:** Push to main/develop, or pull requests
- **Actions:**
  - Tests release build process
  - Verifies package structure
  - Checks package size (must be < 1MB)
  - Uploads test artifact

## Scripts

| Script | Purpose |
|--------|---------|
| `poetry run build-release` | Build deployment package (version from pyproject.toml) |
| `install.sh [install_dir]` | Install on target system (default: `/opt/pisolar`) |
