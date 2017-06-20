from Config import addFilter
# RPMs built from git have no %changelog, the proper ones maintained from dist-git do though
addFilter(r'no-changelogname-tag')
# RPMs built from git have no source tarball uploaded to PYPI
addFilter(r'invalid-url')
