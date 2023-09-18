%global package_speccommit 7241713e2285e29dfb1059b42070635a26477801
%global package_srccommit v2.8.74

Summary: A set of system configuration and setup files
Name: setup
Version: 2.8.74
Release: 1%{?xsrel}%{?dist}
License: Public Domain
Group: System Environment/Base
URL: https://pagure.io/setup/
Source0: setup-2.8.74.tar.gz
BuildArch: noarch
BuildRequires: bash perl
#require system release for saner dependency order
Requires: system-release
Conflicts: filesystem < 3
Conflicts: initscripts < 4.26, bash <= 2.0.4-21

%description
The setup package contains a set of important system configuration and
setup files, such as passwd, group, and profile.

%prep
%autosetup -p1 -n %{name}-%{version}

./shadowconvert.sh

%build

%check
# Run any sanity checks.
make check

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/etc/profile.d
cp -ar * %{buildroot}/etc
rm -f %{buildroot}/etc/uidgid
rm -f %{buildroot}/etc/COPYING
mkdir -p %{buildroot}/var/log
touch %{buildroot}/var/log/lastlog
touch %{buildroot}/etc/environment
chmod 0644 %{buildroot}/etc/environment
chmod 0400 %{buildroot}/etc/{shadow,gshadow}
chmod 0644 %{buildroot}/var/log/lastlog
touch %{buildroot}/etc/fstab
touch %{buildroot}/etc/subuid
touch %{buildroot}/etc/subgid
echo "#Add any required envvar overrides to this file, it is sourced from /etc/profile" >%{buildroot}/etc/profile.d/sh.local
echo "#Add any required envvar overrides to this file, is sourced from /etc/csh.login" >%{buildroot}/etc/profile.d/csh.local


# remove unpackaged files from the buildroot
rm -f %{buildroot}/etc/Makefile
rm -f %{buildroot}/etc/serviceslint
rm -f %{buildroot}/etc/uidgidlint
rm -f %{buildroot}/etc/shadowconvert.sh
rm -f %{buildroot}/etc/setup.spec
# remove the "originals" of patched files
rm -f %{buildroot}/etc/securetty.mainframe
rm -f %{buildroot}/etc/bashrc.envvar
rm -f %{buildroot}/etc/*.orig

#throw away useless and dangerous update stuff until rpm will be able to
#handle it ( http://rpm.org/ticket/6 )
# Before discarding the rpmnew files, check them for updates
%post -p <lua>
grps={}
egrps={}
users={}
-- A function to avoid supplying nil arguments
function nn(a, s)
  if s == nil then
    return ""
  end
  return string.format("%s '%s' ", a, s)
end
-- LUA doesn't have split() so we have to make our own
function split(str, pat)
   local t = {}
   local fpat = "(.-)" .. pat
   local last_end = 1
   local s, e, cap = str:find(fpat, 1)
   while s do
      if s ~= 1 or cap ~= "" then
         table.insert(t, cap)
      end
      last_end = e+1
      s, e, cap = str:find(fpat, last_end)
   end
   if last_end <= #str then
      cap = str:sub(last_end)
      table.insert(t, cap)
   end
   return t
end
-- Gather the set of NEW users (which are in the new passwd file but not in the old)
-- NOTE this can only happen on upgrade, so there is no chance of us trying to
-- invoke the body before coreutils is available.
if posix.access("/etc/passwd.rpmnew", "r") then
  os.remove("%{_localstatedir}/lib/rpm-state/setup-newusrs")
  os.execute("bash -c 'comm -13 <(sort -u /etc/passwd) <(sort -u /etc/passwd.rpmnew)' > %{_localstatedir}/lib/rpm-state/setup-newusrs")
  for line in io.lines("%{_localstatedir}/lib/rpm-state/setup-newusrs") do
    local u = split(line, ":")
    -- Name maps to UID, GID, comment, homedir, shell
    users[u[1]] = { u[3], u[4], u[5], u[6], u[7] }
  end
  os.remove("%{_localstatedir}/lib/rpm-state/setup-newusrs")
end
-- Get the set of NEW groups (which are in the new group file but not in the old)
-- NOTE as above, this can only be invoked on upgrade
if posix.access("/etc/group.rpmnew", "r") then
  os.remove("%{_localstatedir}/lib/rpm-state/setup-newgrp")
  os.execute("bash -c 'comm -13 <(sort -u /etc/group) <(sort -u /etc/group.rpmnew)' > %{_localstatedir}/lib/rpm-state/setup-newgrp")
  for line in io.lines("%{_localstatedir}/lib/rpm-state/setup-newgrp") do
    local g = split(line, ":")
    -- Name maps to GID.
    grps[g[1]] = g[3]
  end
  os.remove("%{_localstatedir}/lib/rpm-state/setup-newgrp")
  -- Since we are upgrading and therefore have a changed group set,
  -- read the definitive set of which extra groups users should be in
  for line in io.lines("/etc/group.rpmnew") do
    local g = split(line, ":")
    if #g > 3 then
      -- For each user we find, add this group to their set
      for v in g[4]:gmatch('[^,]+') do
        if egrps[v] ~= nil then
          table.insert(egrps[v], g[1])
        else
          egrps[v] = { g[1] }
        end
      end
    end
  end
end
-- These work sections are guaranteed only to be called on upgrade, because
-- the lists will be empty otherwise.
-- Add any groups which need adding
for k, v in pairs(grps) do
  os.execute(string.format("/usr/sbin/groupadd -g %d -r -f %s", v, k))
end
-- Add any users which need adding
for k, v in pairs(users) do
  os.execute(string.format("/usr/sbin/useradd -u %d -g %d -r %s%s%s%s", v[1], v[2], nn('-c', v[3]), nn('-d', v[4]), nn('-s', v[5]), k))
end
-- Ensure that the "extra" groups are correct if there has been a change
for k, v in pairs(egrps) do
  os.execute(string.format("/usr/sbin/usermod -G %s %s", table.concat(v, ','), k))
end
-- Now remove any additional password database file entirely
-- RPM warnings about /etc/foo.rpmnew can therefore be ignored
for i, name in ipairs({"passwd", "shadow", "group", "gshadow"}) do
     os.remove("/etc/"..name..".rpmnew")
end
if posix.access("/usr/bin/newaliases", "x") then
  os.execute("/usr/bin/newaliases >/dev/null")
end

%files
%defattr(-,root,root,-)
%doc uidgid COPYING
%verify(not md5 size mtime) %config(noreplace) /etc/passwd
%verify(not md5 size mtime) %config(noreplace) /etc/group
%verify(not md5 size mtime) %attr(0000,root,root) %config(noreplace,missingok) /etc/shadow
%verify(not md5 size mtime) %attr(0000,root,root) %config(noreplace,missingok) /etc/gshadow
%verify(not md5 size mtime) %config(noreplace) /etc/subuid
%verify(not md5 size mtime) %config(noreplace) /etc/subgid
%config(noreplace) /etc/services
%verify(not md5 size mtime) %config(noreplace) /etc/exports
%config(noreplace) /etc/aliases
%config(noreplace) /etc/environment
%config(noreplace) /etc/filesystems
%config(noreplace) /etc/host.conf
%verify(not md5 size mtime) %config(noreplace) /etc/hosts
%config(noreplace) /etc/hosts.allow
%config(noreplace) /etc/hosts.deny
%verify(not md5 size mtime) %config(noreplace) /etc/motd
%config(noreplace) /etc/printcap
%verify(not md5 size mtime) %config(noreplace) /etc/inputrc
%config(noreplace) /etc/bashrc
%config(noreplace) /etc/profile
%config(noreplace) /etc/protocols
%attr(0600,root,root) %config(noreplace,missingok) /etc/securetty
%config(noreplace) /etc/csh.login
%config(noreplace) /etc/csh.cshrc
%dir /etc/profile.d
%config(noreplace) /etc/profile.d/sh.local
%config(noreplace) /etc/profile.d/csh.local
%config(noreplace) %verify(not md5 size mtime) /etc/shells
%ghost %attr(0644,root,root) %verify(not md5 size mtime) /var/log/lastlog
%ghost %verify(not md5 size mtime) %config(noreplace,missingok) /etc/fstab

%changelog
* Mon Apr 03 2023 Deli Zhang <dzhang@tibco.com> - 2.8.74-1
- CP-42642: Add certusers group

* Fri Mar 31 2023 Ming Lu <ming.lu@cloud.com> - 2.8.73-1
- CP-42024: Add telemetry user and group

* Wed Mar 29 2023 Tim Smith <tim.smith@citrix.com> - 2.8.72-2
- CP-42509 Merge new passwd and group files on package update

* Fri Mar 10 2023 Tim Smith <tim.smith@citrix.com> - 2.8.72-1
- Rebuild and move sources

* Tue Mar 07 2023 Deli Zhang <dzhang@tibco.com> - 2.8.71-10
- CP-41888: Add nagios and nrpe users/groups

* Tue Mar 07 2023 Deli Zhang <dzhang@tibco.com> - 2.8.71-9
- CP-41888: Import initial package
