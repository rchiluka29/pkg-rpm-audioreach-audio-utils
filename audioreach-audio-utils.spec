%global debug_package %{nil}
%global commit      16d37f2ff604c0c5e21eb535cf7c6c9c58c26caf
%global shortcommit %(c=%{commit}; echo ${c:0:8})
%global commitdate  20241030

Name:           audioreach-audio-utils
Version:        0^%{commitdate}git%{shortcommit}
Release:        1%{?dist}
Summary:        AudioReach audio route library
License:        BSD-3-Clause-Clear
URL:            https://github.com/AudioReach/audioreach-audio-utils
Source0:        https://github.com/AudioReach/audioreach-audio-utils/archive/%{commit}/%{name}-%{version}.tar.gz

ExclusiveArch:  aarch64

BuildRequires:  autoconf
BuildRequires:  automake
BuildRequires:  libtool
BuildRequires:  make
BuildRequires:  gcc
BuildRequires:  pkgconfig
BuildRequires:  expat-devel
BuildRequires:  pkgconfig(tinyalsa)

%description
AudioReach audio route library (libaudioroute) for configuring
audio routing on Qualcomm platforms. Built from the audio-route
component of audioreach-audio-utils.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
Development headers and pkg-config file for building applications
that use the AudioReach audio route library.

%prep
%autosetup -n %{name}-%{version}

%build
pushd audio-route
autoreconf -fi
%configure --disable-static
%make_build
popd

%install
pushd audio-route
%make_install
popd
find %{buildroot} -name '*.la' -delete

%files
%license LICENSE
%{_libdir}/libaudioroute.so

%files devel
%{_includedir}/audio_route/
%{_libdir}/pkgconfig/audioroute.pc

%changelog
* Wed Oct 30 2024 Qualcomm Linux <quic_linux@quicinc.com> - 0^20241030git16d37f2f-1
- Initial RPM packaging of audioreach-audio-utils for AudioReach components
