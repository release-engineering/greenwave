
%global upstream_version 0.6.1

Name:           greenwave
Version:        0.6.1
Release:        1%{?dist}
Summary:        Service for gating on automated tests
License:        GPLv2+
URL:            https://pagure.io/greenwave
Source0:        https://files.pythonhosted.org/packages/source/g/%{name}/%{name}-%{upstream_version}.tar.gz

BuildRequires:  python2-devel
%{?systemd_requires}
BuildRequires:  systemd
%if 0%{?fedora} || 0%{?rhel} > 7
BuildRequires:  python2-setuptools
BuildRequires:  python2-sphinx
BuildRequires:  python2-sphinxcontrib-httpdomain
%if 0%{?fedora} >= 27
BuildRequires:  python2-sphinxcontrib-issuetracker
%else # old name
BuildRequires:  python-sphinxcontrib-issuetracker
%endif
BuildRequires:  python2-flask
BuildRequires:  python2-pytest
BuildRequires:  python2-requests
%if 0%{?fedora} >= 28
BuildRequires:  python2-pyyaml
%else # old name
BuildRequires:  PyYAML
%endif
BuildRequires:  python2-dogpile-cache
%else # EPEL7 uses python- naming
BuildRequires:  python-setuptools
BuildRequires:  python-flask
BuildRequires:  pytest
BuildRequires:  python-requests
BuildRequires:  PyYAML
BuildRequires:  python-dogpile-cache
%endif
BuildRequires:  fedmsg
BuildArch:      noarch
%if 0%{?fedora} || 0%{?rhel} > 7
Requires:  python2-flask
Requires:  python2-requests
%if 0%{?fedora} >= 28
Requires:  python2-pyyaml
%else # old name
Requires:  PyYAML
%endif
Requires:  python2-dogpile-cache
%else # EPEL7 uses python- naming
Requires:  python-flask
Requires:  python-requests
Requires:  PyYAML
Requires:  python-dogpile-cache
%endif
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
