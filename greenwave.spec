
%global upstream_version 0.9.12

Name:           greenwave
Version:        0.9.12
Release:        1%{?dist}
Summary:        Service for gating on automated tests
License:        GPLv2+
URL:            https://pagure.io/greenwave
Source0:        https://files.pythonhosted.org/packages/source/g/%{name}/%{name}-%{upstream_version}.tar.gz

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-sphinx
BuildRequires:  python3-sphinxcontrib-httpdomain
BuildRequires:  python3-sphinxcontrib-issuetracker
BuildRequires:  python3-flask
BuildRequires:  python3-pytest
BuildRequires:  python3-requests
BuildRequires:  python3-PyYAML
BuildRequires:  python3-dogpile-cache
BuildRequires:  python3-fedmsg
BuildRequires:  python3-prometheus_client
BuildArch:      noarch
Requires:  python3-flask
Requires:  python3-requests
Requires:  python3-PyYAML
Requires:  python3-dogpile-cache
Requires:  python3-fedmsg
Requires:  python3-prometheus_client

%description
Greenwave is a service for gating on automated tests by querying ResultsDB and
WaiverDB.

%prep
%setup -q -n %{name}-%{upstream_version}

%build
%py3_build
DEV=true GREENWAVE_CONFIG=$(pwd)/conf/settings.py.example make -C docs SPHINXOPTS= html text

%install
%py3_install

%check
export PYTHONPATH=%{buildroot}/%{python3_sitelib}
py.test-3 greenwave/tests/

%files
%license COPYING
%doc README.md conf
%doc docs/_build/html docs/_build/text
%{python3_sitelib}/%{name}
%{python3_sitelib}/%{name}*.egg-info
%{_sysconfdir}/fedmsg.d/*

%changelog
