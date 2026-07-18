%define name netflix-client
%define version 1.0.0
%define release 1
%define _prefix /usr

Name: %{name}
Version: %{version}
Release: %{release}
Summary: Native Netflix desktop client for Linux
License: MIT
URL: https://github.com/netflix-client/netflix-client
Source0: %{name}-%{version}.tar.gz
BuildArch: noarch
Requires: python3 >= 3.12
Requires: python3-pyside6 >= 6.6
Requires: python3-pyside6-qtwebengine >= 6.6
Requires: python3-keyring
Requires: python3-platformdirs
Requires: libnotify

%description
A native-feeling Linux desktop client for Netflix built with Python
and Qt (PySide6). Integrates deeply with the desktop environment
including system tray, MPRIS media controls, global shortcuts,
and native notifications.

%install
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_datadir}/applications
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/scalable/apps
mkdir -p %{buildroot}%{_datadir}/%{name}

cp -r app %{buildroot}%{_datadir}/%{name}/
install -m 755 netflix-client.py %{buildroot}%{_bindir}/netflix-client
install -m 644 packaging/netflix-client.desktop %{buildroot}%{_datadir}/applications/
install -m 644 app/assets/icon.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/netflix-client.svg

%files
%{_bindir}/netflix-client
%{_datadir}/applications/netflix-client.desktop
%{_datadir}/icons/hicolor/scalable/apps/netflix-client.svg
%{_datadir}/%{name}/
