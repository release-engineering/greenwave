
%global upstream_version 0.0

Name:           greenwave
Version:        0.0
Release:        1%{?dist}
Summary:        Service for gating on automated tests
License:        GPLv2+
URL:            https://pagure.io/greenwave
Source0:        https://files.pythonhosted.org/packages/source/w/%{name}/%{name}-%{upstream_version}.tar.gz

BuildRequires:  python2-devel
%if 0%{?fedora} || 0%{?rhel} > 7
BuildRequires:  python2-setuptools
BuildRequires:  python2-sphinx
BuildRequires:  python-sphinxcontrib-httpdomain
BuildRequires:  python2-flask
BuildRequires:  python2-pytest
BuildRequires:  python2-requests
%else # EPEL7 uses python- naming
BuildRequires:  python-setuptools
BuildRequires:  python-flask
BuildRequires:  pytest
BuildRequires:  python-requests
%endif
BuildArch:      noarch
%if 0%{?fedora} || 0%{?rhel} > 7
Requires:  python2-flask
Requires:  python2-requests
%else # EPEL7 uses python- naming
Requires:  python-flask
Requires:  python-requests
%endif

%description
Greenwave is a service for gating on automated tests by querying ResultsDB and
WaiverDB.

%prep
%setup -q -n %{name}-%{upstream_version}

%build
%py2_build
%if 0%{?fedora}
make -C docs html text
%endif

%install
%py2_install

%check
export PYTHONPATH=%{buildroot}/%{python2_sitelib}
py.test greenwave/tests/

%files
%license COPYING
%doc README.md conf
%if 0%{?fedora}
%doc docs/_build/html docs/_build/text
%endif
%{python2_sitelib}/%{name}
%{python2_sitelib}/%{name}*.egg-info

%changelog
