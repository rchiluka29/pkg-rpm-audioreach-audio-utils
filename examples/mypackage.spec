Name:           mypackage
Version:        1.0
Release:        1%{?dist}
Summary:        One-line summary of the package

License:        BSD-3-Clause
URL:            https://example.com/mypackage
# Source0's filename must match the entry in `sources`. On a cache miss the
# build downloads this URL, so keep it pointing at a fetchable upstream tarball.
# %{name} and %{version} are expanded, so bumping Version: is usually all you need.
Source0:        https://example.com/mypackage/releases/%{name}-%{version}.tar.gz

BuildRequires:  gcc
BuildRequires:  make

%description
A longer description of the package.

%prep
%autosetup

%build
%configure
%make_build

%install
%make_install

%files
%license LICENSE
%doc README.md
%{_bindir}/mypackage

%changelog
* Mon Jun 29 2026 Maintainer <maintainer@example.com> - 1.0-1
- Initial package
