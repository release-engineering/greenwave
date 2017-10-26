
%global upstream_version 0.3

Name:           greenwave
Version:        0.3
Release:        1%{?dist}
Summary:        Service for gating on automated tests
License:        GPLv2+
URL:            https://pagure.io/greenwave
Source0:        https://files.pythonhosted.org/packages/source/g/%{name}/%{name}-%{upstream_version}.tar.gz

BuildRequires:  python2-devel
%if 0%{?fedora} || 0%{?rhel} > 7
BuildRequires:  python2-setuptools
BuildRequires:  python2-sphinx
BuildRequires:  python-sphinxcontrib-httpdomain
BuildRequires:  python-sphinxcontrib-issuetracker
BuildRequires:  python2-flask
BuildRequires:  python2-pytest
BuildRequires:  python2-requests
%else # EPEL7 uses python- naming
BuildRequires:  python-setuptools
BuildRequires:  python-flask
BuildRequires:  pytest
BuildRequires:  python-requests
%endif
%{?systemd_requires}
BuildRequires:  systemd
BuildRequires:  PyYAML
BuildRequires:  python-dogpile-cache
BuildRequires:  fedmsg
BuildArch:      noarch
%if 0%{?fedora} || 0%{?rhel} > 7
Requires:  python2-flask
Requires:  python2-requests
%else # EPEL7 uses python- naming
Requires:  python-flask
Requires:  python-requests
%endif
Requires:  PyYAML
Requires:  python-dogpile-cache
Requires:  fedmsg

%description
Greenwave is a service for gating on automated tests by querying ResultsDB and
WaiverDB.

%prep
%setup -q -n %{name}-%{upstream_version}

%build
%py2_build
%if 0%{?fedora}
make -C docs SPHINXOPTS= html text
%endif

%install
%py2_install
install -d %{buildroot}%{_unitdir}
install -m0644 \
    systemd/%{name}.service \
    systemd/%{name}.socket \
    %{buildroot}%{_unitdir}

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
%{_unitdir}/%{name}.service
%{_unitdir}/%{name}.socket
%{_sysconfdir}/fedmsg.d/*

%post
%systemd_post %{name}.service
%systemd_post %{name}.socket

%preun
%systemd_preun %{name}.service
%systemd_preun %{name}.socket

%postun
%systemd_postun_with_restart %{name}.service

%changelog
