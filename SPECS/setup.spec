# XCP-ng comment:
# XenServer forked v2.8.71-9 from CentOS 7, then started incrementing the
# version numbers, based on their own internal tarball releases.
# This is not a packaging practice that we want to follow at XCP-ng.
# A package should either follow upstream versioning, or be renamed
# to indicate that it is a fork, with its own releases.
# So we'll still version it as 2.8.71 for now.
%define xs_version 2.8.74

Summary: A set of system configuration and setup files
Name: setup
Version: 2.8.71
Release: 9.1%{?dist}
License: Public Domain
Group: System Environment/Base
URL: https://pagure.io/setup/
# This is actually 2.8.71 with CentOS patches applied, repackaged and modified by XenServer
Source0: setup-%{xs_version}.tar.gz

# XCP-ng patches
Patch1000: setup-2.8.74.xs-delete-telemetry-user-and-group.XCP-ng.patch

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
%autosetup -p1 -n %{name}-%{xs_version}

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
* Tue Jun 04 2024 Samuel Verschelde <stormi-xcp@ylix.fr> - 2.8.71-9.1
- Rebase on XenServer's 2.8.74-1, but keep versioning consistent with CentOS 7
- Restore upstream CentOS changelog, that had been deleted by XenServer
- Add setup-2.8.74-delete-telemetry-user-and-group.XCP-ng.patch
- *** XenServer changelog ***
- * Mon Apr 03 2023 Deli Zhang <dzhang@tibco.com> - 2.8.74-1
- - CP-42642: Add certusers group
- * Fri Mar 31 2023 Ming Lu <ming.lu@cloud.com> - 2.8.73-1
- - CP-42024: Add telemetry user and group
- * Wed Mar 29 2023 Tim Smith <tim.smith@citrix.com> - 2.8.72-2
- - CP-42509 Merge new passwd and group files on package update
- * Fri Mar 10 2023 Tim Smith <tim.smith@citrix.com> - 2.8.72-1
- - Rebuild and move sources
- * Tue Mar 07 2023 Deli Zhang <dzhang@tibco.com> - 2.8.71-10
- - CP-41888: Add nagios and nrpe users/groups
- * Tue Mar 07 2023 Deli Zhang <dzhang@tibco.com> - 2.8.71-9
- - CP-41888: Import initial package

* Wed Nov 22 2017 Ondrej Vasik <ovasik@redhat.com> - 2.8.71-9
- change the URL of the upstream (#1502427)

* Fri Nov 17 2017 Ondrej Vasik <ovasik@redhat.com> - 2.8.71-8
- fix group id for tape in /etc/group (should be 33) (#1433020)
- provide a way how to override set envvars through sh.local file(#1344007)
- provide a way how to override set ennvars through csh.local file

* Wed May 04 2016 Ondrej Vasik <ovasik@redhat.com> - 2.8.71-7
- add basic empty subuid/subgid files for docker (#1311278)
- specify full path to utilities in /etc/profile and /etc/bashrc
  (#1331871)

* Fri May 22 2015 Ondrej Vasik <ovasik@redhat.com> - 2.8.71-6
- change reservation of 185:185 to jboss user (#1192413)
- reserve uidgid pair 167:167 for ceph (#1221043)
- reserve uidgid for systemd-network(192:192) (#1213820)
- reserve uidgid for systemd-resolve(193:193) (#1213820)
- mention systemd-jounal-gateway can be dynamic (#1213820) 


* Fri Aug 15 2014 Ondrej Vasik <ovasik@redhat.com> - 2.8.71-5
- reserve uidgid pair 142:142 for activemq (#1086923)
- add xfs to /etc/filesystems, fallback to /proc/filesystems
  (#1123832)

* Wed Mar 12 2014 Ondrej Vasik <ovasik@redhat.com> - 2.8.71-4
- require system-release for saner dependency order (#1075578)

* Tue Feb 25 2014 Ondrej Vasik <ovasik@redhat.com> - 2.8.71-3
- add more securetty required for mainframes (#1067347)
- set SHELL envvar to /bin/bash in bashrc (#1063552)

* Fri Dec 27 2013 Daniel Mach <dmach@redhat.com> - 2.8.71-2
- Mass rebuild 2013-12-27

* Fri Jun 07 2013 Ondrej Vasik <ovasik@redhat.com> 2.8.71-1
- fix escape codes for screen (#969429)
- handle vte terminals in bashrc (#924275)

* Tue May 14 2013 Ondrej Vasik <ovasik@redhat.com> 2.8.70-1
- fix typo in cdrom default group (#962486)

* Thu Apr 18 2013 Ondrej Vasik <ovasik@redhat.com> 2.8.69-1
- remove the rpmlib(X-CheckUnifiedSystemdir) requirement
  hack - no longer required

* Sun Apr 14 2013 Ondrej Vasik <ovasik@redhat.com> 2.8.68-1
- assign gid :135 for mock (#928063)
- update /etc/services to latest IANA reservations

* Wed Mar 20 2013 Ondrej Vasik <ovasik@redhat.com> 2.8.67-1
- assign 166:166 uidgid pair for ceilometer (#923891)
- change 187:187 reservation from openstack-heat
  to just heat(#923858)
- longer shell names support caused by UsrMove to
  the /etc/shells (#922527)
- drop gopher (uid 13, gid 30) from groups created by default
  -> dropped completely - no gopher server in Fedora (#918206)
- drop dip (gid 40) from groups created by default
  -> moved to ppp (#918206)
- drop uucp (uidgid 14) from groups created by default
  -> moved to uucp (#918206)
- create cdrom, tape, dialout, floppy groups in setup(#919285)

* Tue Mar 05 2013 Ondrej Vasik <ovasik@redhat.com> 2.8.66-1
- assign :190 gid for systemd-journal (#918120)
- assign 191:191 uidgid pair for systemd-journal-gateway (#918120)

* Wed Jan 23 2013 Ondrej Vasik <ovasik@redhat.com> 2.8.65-1
- assign 165:165 uidgid pair for cinder (#902987)

* Wed Jan 16 2013 Ondrej Vasik <ovasik@redhat.com> 2.8.64-1
- correct handling of 256 color terminals in bashrc

* Mon Dec 02 2012 Ondrej Vasik <ovasik@redhat.com> 2.8.63-1
- ovirtagent created by ovirt-guest-agent

* Mon Dec 02 2012 Ondrej Vasik <ovasik@redhat.com> 2.8.62-1
- rename rhevagent uidgid reservation to ovirtagent

* Fri Nov 02 2012 Ondrej Vasik <ovasik@redhat.com> 2.8.61-1
- reserve uid 189 for hacluster (#872208)
- reserve gid 189 for haclient (#872208)

* Tue Oct 02 2012 Ondrej Vasik <ovasik@redhat.com> 2.8.60-1
- reserve 188:188 for haproxy (#860221)

* Wed Sep 19 2012 Ondrej Vasik <ovasik@redhat.com> 2.8.59-1
- update /etc/services to match with latest IANA
  assignments

* Mon Aug 21 2012 Ondrej Vasik <ovasik@redhat.com> 2.8.58-1
- reserve 110:110 for jetty (#849927)

* Mon Aug 06 2012 Ondrej Vasik <ovasik@redhat.com> 2.8.57-1
- reserve 187:187 for openstack-heat (#845078)

* Sat Jul 21 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.8.56-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Fri Jul 13 2012 Ondrej Vasik <ovasik@redhat.com> 2.8.56-1
- Turn on parallel history in bash (#815810)

* Thu Jul 12 2012 Ondrej Vasik <ovasik@redhat.com> 2.8.55-1
- reserve 186 uid for jbosson-agent user, reserve 186 gid
  for jbosson group (#839410)

* Fri May 11 2012 Ondrej Vasik <ovasik@redhat.com> 2.8.54-1
- use unset -f pathmunge in /etc/profile to work more nicely
  with ksh (#791140)

* Wed Apr 11 2012 Ondrej Vasik <ovasik@redhat.com> 2.8.53-1
- reserve 185:185 for jboss-as (#809398)

* Fri Mar 23 2012 Ondrej Vasik <ovasik@redhat.com> 2.8.52-1
- reserve 184:184 for mongodb (#806052)

* Thu Mar 22 2012 Ondrej Vasik <ovasik@redhat.com> 2.8.51-1
- do not throw away the stderr output of profile.d scripts
  in noninteractive bash/ksh sessions(#805507)

* Mon Mar 19 2012 Ondrej Vasik <ovasik@redhat.com> 2.8.50-1
- reserve 182:182 for katello (#804204)
- reserve 183:183 for elasticsearch (#804205)

* Tue Feb 21 2012 Ondrej Vasik <ovasik@redhat.com> 2.8.49-1
- conflict with filesystems before usrmove change

* Sun Feb 12 2012 Ondrej Vasik <ovasik@redhat.com> 2.8.48-1
- remove /bin and /sbin from /etc/profile(#789616)
- require usrmove
- add sbin paths in csh.login consistently with bash(#773268)

* Tue Jan 10 2012 Ondrej Vasik <ovasik@redhat.com> 2.8.47-1
- reserve 181:181 uidgid pair for wallaby (#772747)

* Tue Dec 06 2011 Ondrej Vasik <ovasik@redhat.com> 2.8.46-1
- reserve 134:134 uidgid pair for cimsrvr (#760178)

* Fri Nov 25 2011 Ondrej Vasik <ovasik@redhat.com> 2.8.45-1
- reserve :156 groupid for stapusr - #756807
- reserve :157 groupid for stapsys - #756807
- reserve :158 groupid for stapdev - #756807

* Wed Nov 16 2011 Ondrej Vasik <ovasik@redhat.com> 2.8.44-1
- reserve 180:180 for aeolus - #754274

* Fri Nov 11 2011 Ondrej Vasik <ovasik@redhat.com> 2.8.43-1
- gopher home dir in uidgid should be /var/gopher - #752885
- reserve 163:163 for keystone (openstack-keystone) - #752842
- reserve 164:164 for quantum (openstack-quantum) - #752842
- update services to latest IANA

* Wed Nov  2 2011 Ondrej Vasik <ovasik@redhat.com> 2.8.42-1
- add ext4 to /etc/filesystems - #750506

* Wed Sep 14 2011 Ondrej Vasik <ovasik@redhat.com> 2.8.41-1
- reserve 179:179 for sanlock - #727655

* Fri Aug 26 2011 Ondrej Vasik <ovasik@redhat.com> 2.8.40-1
- reserve 178:178 for myproxy (myproxy-server) - #733671

* Fri Aug 26 2011 Ondrej Vasik <ovasik@redhat.com> 2.8.39-1
- reserve 177:177 for dhcpd (dhcp) - #699713

* Tue Aug 23 2011 Ondrej Vasik <ovasik@redhat.com> 2.8.38-1
- reserve 160:160 for swift (openstack-swift) - #732442
- reserve 161:161 for glance (openstack-glance) - #732442
- reserve 162:162 for nova (openstack-nova) - #732442
- comment out 0/tcp spr-itunes /etc/services entry (#710185)
- add hvc[01], xvc0, hvsi[012] to /etc/securetty (#728030)

* Tue Aug 16 2011 Ondrej Vasik <ovasik@redhat.com> 2.8.37-1
- dropped all suplemental groups from basic /etc/group file
  (#722529)

* Tue Aug 16 2011 Ondrej Vasik <ovasik@redhat.com> 2.8.36-1
- dropped suplemental root's groups(#722529)

* Wed Jun 29 2011 Ondrej Vasik <ovasik@redhat.com> 2.8.35-1
- reserve 176:176 for apache traffic server - ats(#715266)

* Mon Jun 13 2011 Ondrej Vasik <ovasik@redhat.com> 2.8.34-1
- update protocols and services to latest IANA
- reserve 175:175 for rhevagent (#709599)

* Thu May 19 2011 Ondrej Vasik <ovasik@redhat.com> 2.8.33-1
- reflect the reserved username change of amanda
  to amandabackup (#700807)
- drop order hosts,bind from setup, no longer used by
  glibc (#703049)
- assign 174:174 uidgid for user/group retrace
  (abrt retrace-server, #706012)

* Tue Apr 12 2011 Ondrej Vasik <ovasik@redhat.com> 2.8.32-1
- do not override already set PROMPT_COMMAND envvar(#691425)
- do not quit uidgidlint after first error, show all
- update services to latest IANA

* Mon Jan 24 2011 Ondrej Vasik <ovasik@redhat.com> 2.8.31-1
- drop ownership of /etc/mtab, now owned by util-linux

* Tue Jan 18 2011 Ondrej Vasik <ovasik@redhat.com> 2.8.30-1
- remove explicit buildroot
- reserve uidgid pair 173:173 for abrt(#670231)

* Fri Dec 03 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.29-1
- run newaliases in the post to prevent sendmail messages
  about old alias database in the log(#658921)

* Fri Nov 12 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.28-1
- update services and protocols to latest IANA reservations
- reserve uidgid pair 109:109 for rhevm(#652287)

* Tue Sep 07 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.27-1
- add double quotes arround sourced profile.d scripts -
  allow special characters in script names

* Wed Aug 18 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.26-1
- fix regression in the change to printf(#624900)

* Thu Aug 12 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.25-1
- use printf instead of echo in bashrc scripts(#620435)
- update services to latest IANA

* Wed Jul 28 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.24-1
- do show messages from profile.d scripts in interactive
  login ksh shell(#616418)
- respect umask settings even with login shell

* Tue Jun 29 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.23-1
- reserve uidgid pair 172:172 for rtkit (#609171)

* Tue Jun 15 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.22-1
- reserve uidgid pair 170:170 for avahi-autoipd
- reserve uidgid pair 171:171 for pulse (pulseaudio)
- update reserved homedir for avahi

* Mon Jun 07 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.21-1
- update name of group reserved by cyrus-imapd to saslauth

* Mon May 24 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.20-1
- speedup pathmunge() by using portable case(#544652)

* Wed May 19 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.19-1
- fix syntax error in bashrc pathmunge(since bash 3.2)(#592799)

* Tue Apr 27 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.18-1
- reserve uidgid pair 140:140 for ricci daemon(#585957)
- reserve uidgid pair 141:141 for luci daemon(#585958)

* Wed Mar 31 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.17-1
- verify md5sum/size/mtime in the case of /etc/hosts.allow
  and /etc/hosts.deny (#578263)
- do the same for /etc/services and /etc/protocols, we
  provide (almost) complete IANA set, so no reason to modify
  it in most cases outside of setup package

* Fri Mar 26 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.16-3
- bad ugly double-thirteen friday(fix previous badfix)

* Fri Mar 26 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.16-2
- fix not set path for csh shell caused by 2.8.16 update

* Fri Mar 26 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.16-1
- drop X11R6 hierarchy dir from tcsh path (#576940)
- update services to latest IANA
- update protocols to latest IANA

* Thu Jan 21 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.15-1
- reserve uidgid pair 155:155 for stap-server(#555813)
- reserve uidgid pair 113:113 for usbmuxd(#556525)

* Tue Jan 12 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.14-1
- reserve uidgid pair 133:133 for bacula(#554705)

* Tue Jan 05 2010 Ondrej Vasik <ovasik@redhat.com> 2.8.13-1
- update services to latest IANA
- avoid one /usr/bin/id stat call in /etc/profile(#549056)

* Thu Dec 17 2009 Ondrej Vasik <ovasik@redhat.com> 2.8.12-1
- speed up pathmunge inside bashrc (#544652)
- do not use deprecated egrep in profile

* Thu Dec 03 2009 Ondrej Vasik <ovasik@redhat.com> 2.8.11-1
- don't have HISTCONTROL ignorespace by default (#520632),
  but do not override it when it is already set
- add csync alias for port 2005 / tcp, udp

* Wed Nov 11 2009 Ondrej Vasik <ovasik@redhat.com> 2.8.10-1
- reserve uidgid pair 112:112 for vhostmd (#534110)
- update /etc/services to latest IANA

* Tue Sep 08 2009 Ondrej Vasik <ovasik@redhat.com> 2.8.9-1
- reserve uidgid pair 108:108 for ovirt from libvirt (#513261)
- reserve uidgid pair 111:111 for saned from sane-backends
  (#520634)

* Mon Aug 17 2009 Ondrej Vasik <ovasik@redhat.com> 2.8.8-1
- change permissions on /etc/shadow and /etc/gshadow to 0000 and
  use capabilities for them(#517577)

* Sun Jul 26 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.8.7-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_12_Mass_Rebuild

* Tue Jul 21 2009 Ondrej Vasik <ovasik@redhat.com> 2.8.7-1
- increase threshold for uidgid reservations to 200
- reserve uidgid pair 107:107 for qemu (libvirt,#511957)
- reflect threshold in profile and bashrc, do inform about
  uidgid file existence there
- remove old remnants about portmap from hosts.deny(#509919)

* Mon Jun 29 2009 Ondrej Vasik <ovasik@redhat.com> 2.8.6-1
- update protocols and services to latest IANA
- add example for tty in prompt(#503304)

* Wed May 20 2009 Ondrej Vasik <ovasik@redhat.com> 2.8.5-1
- use history-search-backward/forward for pageup/pagedown
  mapping in inputrc (#500989)
- add HISTCONTROL="ignoreboth" to /etc/profile to not include
  duplicities and lines starting with space into the history
  (#500819)

* Tue May 12 2009 Ondrej Vasik <ovasik@redhat.com> 2.8.4-1
- add oprofile (16:16) to uidgid
- use os.remove instead of os.execute in lua post
  - no dependency on /bin/sh (thanks Panu Matilainen)

* Wed Apr 22 2009 Ondrej Vasik <ovasik@redhat.com> 2.8.3-2
- rewrite postun scriptlet to <lua> to prevent /bin/sh
  dependency

* Fri Apr 10 2009 Ondrej Vasik <ovasik@redhat.com> 2.8.3-1
- do not disable coredumps in profile/csh.cshrc scripts,
  coredumps already disabled in rawhide's RLIMIT_CORE(#495035)

* Wed Mar 25 2009 Ondrej Vasik <ovasik@redhat.com> 2.8.2-2
- reserve uid 65 for nslcd (will share group 55 ldap, #491899)

* Tue Mar 24 2009 Ondrej Vasik <ovasik@redhat.com> 2.8.2-1
- ship COPYING file, update protocols and services
  to latest IANA

* Mon Mar 23 2009 Ondrej Vasik <ovasik@redhat.com> 2.8.1-2
- fix sources syntax, add sources URL (#226412)

* Thu Feb 26 2009 Ondrej Vasik <ovasik@redhat.com> 2.8.1-1
- do ship/generate /etc/{shadow,gshadow} files(#483251)
- do ship default /etc/hosts with setup (#483244)
- activate multi on (required for IPv6 only localhost
  recognition out-of-the-box) (#486461)
- added postun section for cleaning of dangerous .rpmnew
  files after updates
- make profile and bashrc more portable (ksh, #487419)

* Wed Feb 25 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.7.7-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_11_Mass_Rebuild

* Mon Feb 02 2009 Ondrej Vasik <ovasik@redhat.com> 2.7.7-4
- drop <lua> scriptlet completely(audio/video group
  temporarily created by packages which use it for
  updates(#477769))

* Fri Jan 30 2009 Ondrej Vasik <ovasik@redhat.com> 2.7.7-3
- add support for ctrl+arrow shortcut in rxvt(#474110)

* Thu Jan 29 2009 Ondrej Vasik <ovasik@redhat.com> 2.7.7-2
- reserve 87 gid for polkituser (just uid was reserved),
  reserve 18 gid for dialout(to prevent conflicts with
  polkituser gid)

* Thu Jan 22 2009 Ondrej Vasik <ovasik@redhat.com> 2.7.7-1
- synchronize /etc/services with latest IANA, do not use
  tabs in that file to have consistent output
- fix indentation in /etc/profile and /etc/bashrc
  (#481074)
- assign uid 36 for vdsm, gid 36 for kvm
  (#346151,#481021)

* Tue Jan 20 2009 Ondrej Vasik <ovasik@redhat.com> 2.7.6-1
- make uidgid file better parsable (synchronize tabs)
- reserve gid 11 for group cdrom (udev,MAKEDEV)
- reserve gid 33 for group tape (udev,MAKEDEV)
- reserve gid 87 for group dialout (udev,MAKEDEV)

* Tue Jan 06 2009 Ondrej Vasik <ovasik@redhat.com> 2.7.5-4
- use lua language in post to prevent additional
  dependencies

* Thu Dec 18 2008 Ondrej Vasik <ovasik@redhat.com> 2.7.5-3
- add pkiuser (17:17) to uidgid
- temporarily create video/audio group in post section
  (#476886)

* Wed Dec 10 2008 Ondrej Vasik <ovasik@redhat.com> 2.7.5-2
- do not export PATH twice(#449286 NOTABUG revert)
- do not export INPUTRC(to respect just created ~/.inputrc)
  (#443717)

* Thu Nov 27 2008 Ondrej Vasik <ovasik@redhat.com> 2.7.5-1
- Modified upstream URL, synchronized with upstream git

* Wed Nov 19 2008 Ondrej Vasik <ovasik@redhat.com> 2.7.4-3
- update protocols to latest IANA list (2008-04-18)
- update services to latest IANA list (2008-11-17)
- mark /etc/protocols and /etc/inputrc %%config(noreplace)
- added URL, fixed few rpmlint warnings
- do own audio and video group (#458843), create it in default
  /etc/group

* Tue Nov 18 2008 Ondrej Vasik <ovasik@redhat.com> 2.7.4-2
- again process profile.d scripts in noninteractive shells,
  but do not display stderr/stdout messages(#457243)
- fix wrong prompt for csh/tcsh (#443854)
- don't show error message about missing hostname in profile
  (#301481)
- reserve rquotad port 875 in /etc/services (#455859)
- export PATH after processing profile.d scripts (#449286)
- assign gid's for audio (:63) and video (:39) group(#458843),
  assign uidgid pair (52:52) for puppet (#471918)
- fix /etc/services duplicities to pass serviceslint

* Thu Oct 09 2008 Phil Knirsch <pknirsch@redhat.com> 2.7.4-1
- Include new serviceslint for speedup (#465642)
- Cleaned up services due to newly discovered bugs in it with new serviceslint

* Wed Sep 03 2008 Phil Knirsch <pknirsch@redhat.com> 2.7.3-1
- Added SBinSanity patch as an approved feature (#458176)

* Wed Aug 06 2008 Phil Knirsch <pknirsch@redhat.com> 2.7.2-1
- Added uidgid pair for condor
- Added uidgid pair for trousers

* Fri Jul 25 2008 Phil Knirsch <pknirsch@redhat.com> 2.7.1-1
- Bump to 2.7.1 to avoid version problems with F-9
- Removed group news as well (#437462)

* Tue Jun 17 2008 Phil Knirsch <pknirsch@redhat.com> 2.6.16-1
- Dropped user news from default /etc/passwd (#437462)

* Thu Jun 05 2008 Phil Knirsch <pknirsch@redhat.com> 2.6.15-1
- Added prelude-manager and snortd to uidgid list

* Mon Apr 07 2008 Phil Knirsch <pknirsch@redhat.com> 2.6.14-1
- Updated /etc/services to latest IANA version (#315571)

* Fri Apr 04 2008 Phil Knirsch <pknirsch@redhat.com>
- Fixed a problem with the new prompt for tcsh and screen terminal (#438550)

* Thu Mar 20 2008 Phil Knirsch <pknirsch@redhat.com> 2.6.13-1
- Drop the wrong precmd for csh for xterm and screen terminals

* Tue Feb 26 2008 Phil Knirsch <pknirsch@redhat.com> 2.6.12-1
- Corrected wrong /etc/profile.d behaviour for non-interactive bash and tcsh

* Fri Feb 22 2008 Phil Knirsch <pknirsch@redhat.com> 2.6.11-1
- Fixed problem with /etc/profile.d/* and non-interactive tcsh (#299221)
- Fixed xterm -title problem (#387581)
- Fixed problem with /etc/profile.d/*.csh not being executed for none loginshells anymore
  (#381631, #429838)
- Corrected missing shell for news user in uidgid and passwd

* Thu Aug 16 2007 Phil Knirsch <pknirsch@redhat.com> 2.6.10-1
- License review and update

* Tue Jul 24 2007 Phil Knirsch <pknirsch@redhat.com> 2.6.9-1
- Assigned uid 87 for PolicyKit package (#244950)
- Fixed precmd fix if TERM isn't set (#242732)

* Wed Jun 06 2007 Phil Knirsch <pknirsch@redhat.com> 2.6.7-1
- Fixed precmd setting to behave like bash for (t)csh (#242732)

* Thu May 24 2007 Phil Knirsch <pknirsch@redhat.com> 2.6.6-1
- Added another set of proposed changes to /etc/csh.cshrc (#199817)
- Added missing documentation in /etc/hosts.[allow|deny] (#157053)

* Wed May 23 2007 Phil Knirsch <pknirsch@redhat.com> 2.6.5-1
- Fixed tcsh behaviour for non login shells (#191233)
- Fixed umask setting for tcsh to behave identical to bash logins (#199817)
- Added ipv6-crypt and ipv6-auth for backwards compatibility (#210546)

* Wed Apr 18 2007 Phil Knirsch <pknirsch@redhat.com> 2.6.4-1
- Modified the 111/[tcp/udp] entries to work with rpcbind (#236639)

* Mon Mar 12 2007 Phil Knirsch <pknirsch@redhat.com> 2.6.3-1
- Changed winbind_auth to wbpriv by request of the samba maintainer

* Tue Dec 12 2006 Phil Knirsch <pknirsch@redhat.com> 2.6.2-1.fc7
- Updated uidgid for split of pcap into arpwatcher and tcpdump.

* Tue Nov 28 2006 Phil Knirsch <pknirsch@redhat.com> 2.6.1-1.fc7
- Update version and rebuilt

* Tue Nov 28 2006 Phil Knirsch <pknirsch@redhat.com> 2.5.57-1
- Revert change for umask in /etc/bashrc (#217523)

* Thu Nov 16 2006 Phil Knirsch <pknirsch@redhat.com> 2.5.56-1
- Added an entry for samba and winbind_auth

* Wed Oct 11 2006 Phil Knirsch <pknirsch@redhat.com> 2.5.55-1
- Extended the protocols to include the missing hopopt (#209191)

* Tue Oct 10 2006 Phil Knirsch <pknirsch@redhat.com> 2.5.54-1
- Update /etc/protocols to latest officiall IANA version (#209191)

* Thu Jul 27 2006 Phil Knirsch <pknirsch@redhat.com> 2.5.53-1
- Added utempter gid for new libutempter package (#200240)

* Mon Jun 19 2006 Phil Knirsch <pknirsch@redhat.com> 2.5.52-1
- Lock password for root account by default (#182206)

* Wed May 03 2006 Karsten Hopp <karsten@redhat.de>
- remove gkrellmd from the reserved uid/gid list (#186974)

* Tue Mar 21 2006 Florian La Roche <laroche@redhat.com> 2.5.50-1
- use stricter umask of 022 for all logins

* Thu Feb 23 2006 Phil Knirsch <pknirsch@redhat.com> 2.5.49-1
- Really switch to new /etc/services file
- Added /etc/fstab and /etc/mtab to ownership of setup (#177061)

* Tue Jan 31 2006 Phil Knirsch <pknirsch@redhat.com> 2.5.48-1
- Switched to the new large /etc/services file which fixes #112298, #133683,
  #166443, #168872, #171228.
- Fixed pathmunge problem with bashrc (#123621)
- Removed /usr/X11R6/bin from default PATH (#173856)

* Tue Jan 24 2006 Phil Knirsch <pknirsch@redhat.com>
- Fixed bug with PROMPT_COMMAND being broken for wierd dirs (#142125)
- Added hfsplus to know filesystems (#172820)

* Mon Oct 17 2005 Bill Nottingham <notting@redhat.com>
- make motd noreplace (#170539)

* Tue Sep  6 2005 Bill Nottingham <notting@redhat.com> 2.5.47-1
- make lastlog 0644  (#167200)

* Mon Jun 20 2005 Bill Nottingham <notting@redhat.com> 2.5.46-1
- add buildrequires on bash, tcsh (#161016)
- move core dump size setting from csh.login to csh.cshrc (#156914)

* Fri Jun 17 2005 Bill Nottingham <notting@redhat.com> 2.5.45-1
- ksh doesn't implement EUID/UID. Work around that. (#160731)

* Thu May 19 2005 Bill Nottingham <notting@redhat.com> 2.5.44-1
- fix csh.cshrc when -e is used (#158265)

* Mon Apr 25 2005 Bill Nottingham <notting@redhat.com> 2.5.43-1
- remove mailman aliases (#155841)

* Mon Apr 18 2005 Bill Nottingham <notting@redhat.com> 2.5.42-1
- fix lastlog conflict (#155256)

* Fri Apr 15 2005 Bill Nottingham <notting@redhat.com> 2.5.41-1
- get rid of 'id' error messages if there is no /usr (#142707)

* Mon Jan 31 2005 Bill Nottingham <notting@redhat.com> 2.5.40-1
- have similar prompt changes for su to root in tcsh as in bash (#143826)

* Tue Nov 23 2004 Bill Nottingham <notting@redhat.com> 2.5.39-1
- ghost lastlog (#139539)

* Thu Nov 18 2004 Bill Nottingham <notting@redhat.com> 2.5.38-1
- fix bash/tcsh coredump size inconsistency (#139821)

* Wed Oct 27 2004 Bill Nottingham <notting@redhat.com> 2.5.37-1
- fix inconsistency in profile.d handling (#136859, <agrajag@dragaera.net>)

* Fri Oct  8 2004 Bill Nottingham <notting@redhat.com> 2.5.36-1
- fix duplicate alias

* Tue Sep 28 2004 Bill Nottingham <notting@redhat.com> 2.5.35-1
- add /etc/environment

* Mon Sep 27 2004 Rik van Riel <riel@redhat.com> 2.5.34-2
- mark /etc/services config(noreplace) (#133683)

* Thu Sep 23 2004 Bill Nottingham <notting@redhat.com> 2.5.34-1
- add dict (#107807)
- add cyrus services (#118832)
- move delete-char binding for csh (#113682)
- do the same path munging for csh as for bash (#57708)
- add postfix aliases (#117661)
- fix bashrc login shell check (#104491)
- add odmr to services (#101098)
- add distcc to services (#91535)
- add xterm forware/backward word bindings (#80860)

* Mon May 24 2004 Bill Nottingham <notting@redhat.com>
- make pathmunge available for profile.d scripts (#123621)

* Wed May 19 2004 Joe Orton <jorton@redhat.com> 2.5.33-2
- add IANA Register Port for svn to /etc/services (#122863)

* Wed May  5 2004 Nalin Dahyabhai <nalin@redhat.com> 2.5.33-1
- fix syntax error in csh.cshrc

* Tue May  4 2004 Bill Nottingham <notting@redhat.com> 2.5.32-1
- set MAIL in csh.cshrc (#115376)
- fix inputrc check in csh.login (#115073)

* Mon Jan 26 2004 Bill Nottingham <notting@redhat.com> 2.5.31-1
- move /etc/aliases here

* Mon Dec  8 2003 Bill Nottingham <notting@redhat.com> 2.5.30-1
- remove stty `tput kbs` section (#91357)

* Tue Sep  2 2003 Bill Nottingham <notting@redhat.com> 2.5.27-1
- securetty should be noreplace (#103585)

* Fri Mar 14 2003 Bill Nottingham <notting@redhat.com> 2.5.26-1
- clean up some typos in /etc/services (#86129)

* Mon Feb 17 2003 Florian La Roche <Florian.LaRoche@redhat.de>
- add "console" to /etc/securetty for mainframe

* Mon Jan 20 2003 Nalin Dahyabhai <nalin@redhat.com> 2.5.24-1
- allocate uid/gid for mgetty

* Thu Jan  9 2003 Dan Walsh <dwalsh@redhat.com> 2.5.23-1
- added PXE to /etc/services

* Wed Jan  1 2003 Bill Nottingham <notting@redhat.com> 2.5.22-1
- remove bogus entries from inputrc (#80652)

* Fri Nov 29 2002 Tim Powers <timp@redhat.com> 2.5.21-1
- remove unpackaged files from the buildroot

* Thu Aug 29 2002 Bill Nottingham <notting@redhat.com> 2.5.20-1
- shopt -s checkwinsize everywhere

* Wed Aug 28 2002 Preston Brown <pbrown@redhat.com> 2.5.19-1
- fix bug #61129 (~ substitution)

* Wed Aug 15 2002 Jens Petersen <petersen@redhat.com> 2.5.18-1
- bring back the screen case in /etc/bashrc, since /etc/screenrc no
  longer sets defhstatus (#60596, #60597)

* Sun Aug 11 2002 Florian La Roche <Florian.LaRoche@redhat.de> 2.5.17-1
- add "set mark-symlinked-directories on" to /etc/inputrc

* Mon Jul 22 2002 Phil Knirsch <pknirsch@redhat.com> 2.5.16-2
- Added shopt -s checkwinsize to /etc/bashrc for xterm resizing

* Fri Jul 19 2002 Jens Petersen <petersen@redhat.com> 2.5.16-1
- dont special case screen in /etc/bashrc, since it overrides the user's
  screenrc title setting (#60596)

* Thu Jul 18 2002 Florian La Roche <Florian.LaRoche@redhat.de> 2.5.14-1
- move home dir of "news" to /etc/news

* Tue May 28 2002 Nalin Dahyabhai <nalin@redhat.com> 2.5.13-1
- allocate uid/gid for privilege-separated sshd

* Thu May 23 2002 Tim Powers <timp@redhat.com> 2.5.12-2
- automated rebuild

* Wed Apr  3 2002 Bill Nottingham <notting@redhat.com> 2.5.12-1
- fix misformatted comment in /etc/services, allocate uid/gid for
  frontpage

* Thu Mar 28 2002 Bill Nottingham <notting@redhat.com> 2.5.11-1
- add newline in /etc/shells (#62271)

* Thu Mar 28 2002 Nalin Dahyabhai <nalin@redhat.com> 2.5.10-1
- allocate uid for the vcsa user

* Tue Mar 12 2002 Bill Nottingham <notting@redhat.com> 2.5.9-1
- re-add ext3 to /etc/filesystems

* Mon Mar 11 2002 Bill Nottingham <notting@redhat.com> 2.5.8-1
- add nologin to /etc/shells (#53963)
- fix some quoting issues (#59627)
- fix screen status line (#60596)
- fix path regexps (#59624)
- move profile.d stuff to csh.cshrc (#59946)

* Fri Mar  8 2002 Nalin Dahyabhai <nalin@redhat.com>
- add bprd, bpdbm, bpjava-msvc, vnetd, bpcd, and vopied to /etc/services

* Tue Sep 25 2001 Nalin Dahyabhai <nalin@redhat.com>
- change rmtcfg to an alias for bvcontrol, which is a registered name

* Mon Sep 17 2001 Nalin Dahyabhai <nalin@redhat.com> 2.5.7-1
- add entries to services (ipp, wnn4, and so on)
- try to remove duplicates in services (remove nameserver as alias for domain,
  and readnews as alias for netnews)

* Mon Aug 20 2001 Bill Nottingham <notting@redhat.com>
- change FTP user's home dir to /var/ftp (#52091)
- %%ghost /etc/shadow, /etc/gshadow

* Fri Aug 17 2001 Bill Nottingham <notting@redhat.com>
- add /etc/shells to filelist (#51813)

* Mon Aug 13 2001 Bill Nottingham <notting@redhat.com>
- put lock in /etc/group (#51654)

* Wed Aug  8 2001 Bill Nottingham <notting@redhat.com>
- lock only needs to be a gid
- don't set dspmbyte=euc here; do it in lang.csh, and only if necessary (#50318)

* Mon Aug  6 2001 Jeff Johnson <jbj@redhat.com>
- add lock.lock uid/gid 54 to own /var/lock directory.

* Thu Jul 19 2001 Bill Nottingham <notting@redhat.com>
- add forward/backward-word mappings (#48783)
- add pgpkeyserver port to /etc/services (#49407)

* Thu Jul 19 2001 Preston Brown <pbrown@redhat.com>
- core files disabled by default.  Developers can enable them.

* Fri Jul 13 2001 Bill Nottingham <notting@redhat.com> 2.5.1-1
- revert news user back to no shell (#48701)

* Tue Jul 10 2001 Bill Nottingham <notting@redhat.com> 2.5.0-1
- move profile.d parsing from csh.cshrc to csh.login (#47417)

* Sat Jul  7 2001 Nalin Dahyabhai <nalin@redhat.com> 2.4.15-1
- reorder /etc/services to match comments again
- protocol 118 is stp, not st
- update URLs in /etc/protocols and /etc/services

* Thu Jul  5 2001 Preston Brown <pbrown@redhat.com> 2.4.14-1
- put */sbin in path if user ID is 0.

* Mon Jun 25 2001 Bill Nottingham <notting@redhat.com>
- add an entry to /etc/services for ssh X11 forwarding (#44944)

* Wed Jun 13 2001 Bill Nottingham <notting@redhat.com>
- take ttyS0 out of securetty on main tree

* Tue Jun 12 2001 Philip Copeland <bryce@redhat.com>
- added ttyS0 to securetty for serial console usage

* Tue Jun 12 2001 Bill Nottingham <notting@redhat.com>
- add rndc to /etc/services (#40265)
- test for read bit, not execute bit, for profile.d (#35714)

* Sun Jun 03 2001 Florian La Roche <Florian.LaRoche@redhat.de>
- add "canna" entry to /etc/services

* Mon May 21 2001 Bernhard Rosenkraenzer <bero@redhat.com> 2.4.10-1
- Fix bugs #24159 and #30634 again; whoever moved bashrc from bash
  to setup used an old version. :((

* Wed May  2 2001 Preston Brown <pbrown@redhat.com> 2.4.9-1
- bashrc moved here from bash package
- set umask in bashrc, so it applies for ALL shells.

* Fri Apr 27 2001 Preston Brown <pbrown@redhat.com> 2.4.8-1
- /sbin/nologin for accounts that aren't "real."

* Sat Apr  7 2001 Preston Brown <pbrown@redhat.com>
- revert control-arrow forward/backward word (broken)

* Tue Mar 27 2001 Preston Brown <pbrown@redhat.com>
- fix japanese input with tcsh (#33211)

* Tue Mar  6 2001 Bill Nottingham <notting@redhat.com>
- fix some weirdness with rxvt (#30799)

* Wed Feb 28 2001 Bill Nottingham <notting@redhat.com>
- add SKK input method (#29759)

* Fri Feb 23 2001 Preston Brown <pbrown@redhat.com>

* Wed Feb 21 2001 Bill Nottingham <notting@redhat.com>
- fix inputrc, Yet Again. (#28617)

* Thu Feb 15 2001 Bill Nottingham <notting@redhat.com>
- add in uidgid file, put it in %%doc

* Wed Feb  7 2001 Adrian Havill <havill@redhat.com>
- bindkey for delete in the case of tcsh

* Wed Feb  7 2001 Bill Nottingham <notting@redhat.com>
- add some more stuff to /etc/services (#25396, patch from
  <pekkas@netcore.fi>)

* Tue Feb  6 2001 Nalin Dahyabhai <nalin@redhat.com>
- add gii/tcp = 616 for gated

* Tue Jan 30 2001 Bill Nottingham <notting@redhat.com>
- wrap some inputrc settings with tests for mode, term (#24117)

* Mon Jan 29 2001 Bill Nottingham <notting@redhat.com>
- overhaul /etc/protocols (#18530)
- add port 587 to /etc/services (#25001)
- add corbaloc (#19581)
- don't set /usr/X11R6/bin in $PATH if it's already set (#19968)

* Fri Dec  1 2000 Nalin Dahyabhai <nalin@redhat.com>
- Clean up /etc/services, separating registered numbers from unregistered
  ("squatted") numbers, and adding some.

* Mon Nov 20 2000 Bernhard Rosenkraenzer <bero@redhat.com>
- Add smtps (465/tcp) and submission (587/tcp) to /etc/services for TLS
  support (postfix >= 20001030-2)

* Sun Aug  6 2000 Bill Nottingham <notting@redhat.com>
- /var/log/lastlog is %%config(noreplace) (#15412)
- some of the various %%verify changes (#14819)

* Thu Aug  3 2000 Nalin Dahyabhai <nalin@redhat.com>
- linuxconf should be 98, not 99

* Tue Jul 25 2000 Bill Nottingham <notting@redhat.com>
- fix some of the csh stuff (#14622)

* Sun Jul 23 2000 Nalin Dahyabhai <nalin@redhat.com>
- stop setting "multi on" in /etc/host.conf

* Wed Jul 12 2000 Prospector <bugzilla@redhat.com>
- automatic rebuild

* Tue Jun 27 2000 Bill Nottingham <notting@redhat.com>
- add hfs filesystem

* Wed Jun 21 2000 Preston Brown <pbrown@redhat.com>
- printcap is a noreplace file now

* Sun Jun 18 2000 Bill Nottingham <notting@redhat.com>
- fix typo

* Tue Jun 13 2000 Nalin Dahyabhai <nalin@redhat.com>
- add linuxconf/tcp = 99 to /etc/services

* Sat Jun 10 2000 Bill Nottingham <notting@redhat.com>
- add some stuff to /etc/services
- tweak ulimit call again

* Tue Jun  6 2000 Bernhard Rosenkraenzer <bero@redhat.com>
- homedir of ftp is now /var/ftp

* Sun May 14 2000 Nalin Dahyabhai <nalin@redhat.com>
- move profile.d logic in csh.login to csh.cshrc

* Tue Apr 18 2000 Nalin Dahyabhai <nalin@redhat.com>
- redirect ulimit -S -c to /dev/null to avoid clutter

* Thu Apr 13 2000 Bernhard Rosenkraenzer <bero@redhat.com>
- s/ulimit -c/ulimit -S -c/ - bash 2.x adaption

* Mon Apr 03 2000 Nalin Dahyabhai <nalin@redhat.com>
- Add more of the kerberos-related services from IANA's registry and krb5

* Wed Mar 29 2000 Bernhard Rosenkraenzer <bero@redhat.com>
- Add 2.4'ish vc/* devices to securetty

* Thu Feb 17 2000 Preston Brown <pbrown@redhat.com>
- add /etc/filesystems with sane defaults

* Wed Feb 16 2000 Bill Nottingham <notting@redhat.com>
- don't set prompt in /etc/profile (it's done in /etc/bashrc)

* Fri Feb  5 2000 Bill Nottingham <notting@redhat.com>
- yet more inputrc tweaks from Hans de Goede (hans@highrise.nl)

* Sun Jan 30 2000 Bill Nottingham <notting@redhat.com>
- yet more inputrc tweaks from Hans de Goede (hans@highrise.nl)

* Sun Jan 23 2000 Bill Nottingham <notting@redhat.com>
- fix mailq line. (#7140)

* Fri Jan 21 2000 Bill Nottingham <notting@redhat.com>
- add ldap to /etc/services

* Tue Jan 18 2000 Bill Nottingham <notting@redhat.com>
- kill HISTFILESIZE, it's broken

* Tue Jan 18 2000 Preston Brown <pbrown@redhat.com>
- some inputrc tweaks

* Wed Jan 12 2000 Bill Nottingham <notting@redhat.com>
- make some more stuff noreplace

* Fri Nov 19 1999 Bill Nottingham <notting@redhat.com>
- fix mailq line. (#7140)

* Fri Oct 29 1999 Bill Nottingham <notting@redhat.com>
- split csh.login into csh.login and csh.cshrc (#various)
- fix pop service names (#6206)
- fix ipv6 protocols entries (#6219)

* Thu Sep  2 1999 Jeff Johnson <jbj@redhat.com>
- rename /etc/csh.cshrc to /etc/csh.login (#2931).
- (note: modified /etc/csh.cshrc should end up in /etc/csh.cshrc.rpmsave)

* Fri Aug 20 1999 Jeff Johnson <jbj@redhat.com>
- add defattr.
- fix limit command in /etc/csh.cshrc (#4582).

* Thu Jul  8 1999 Bill Nottingham <notting@redhat.com>
- move /etc/inputrc here.

* Mon Apr 19 1999 Bill Nottingham <notting@redhat.com>
- always use /etc/inputrc

* Wed Mar 31 1999 Preston Brown <pbrown@redhat.com>
- added alias pointing to imap from imap2

* Tue Mar 23 1999 Preston Brown <pbrown@redhat.com>
- updated protocols/services from debian to comply with more modern
- IETF/RFC standards

* Sun Mar 21 1999 Cristian Gafton <gafton@redhat.com>
- auto rebuild in the new build environment (release 4)

* Thu Feb 18 1999 Jeff Johnson <jbj@redhat.com>
- unset variables used in /etc/csh.cshrc (#1212)

* Mon Jan 18 1999 Jeff Johnson <jbj@redhat.com>
- compile for Raw Hide.

* Tue Oct 13 1998 Cristian Gafton <gafton@redhat.com>
- fix the csh.cshrc re: ${PATH} undefined

* Mon Apr 27 1998 Prospector System <bugs@redhat.com>
- translations modified for de, fr, tr

* Fri Dec 05 1997 Erik Troan <ewt@redhat.com>
- /etc/profile uses $i, which needs to be unset

* Mon Nov 03 1997 Donnie Barnes <djb@redhat.com>
- made /etc/passwd and /etc/group %%config(noreplace)

* Mon Oct 20 1997 Erik Troan <ewt@redhat.com>
- removed /etc/inetd.conf, /etc/rpc
- flagged /etc/securetty as missingok
- fixed buildroot stuff in spec file

* Thu Jul 31 1997 Erik Troan <ewt@redhat.com>
- made a noarch package

* Wed Apr 16 1997 Erik Troan <ewt@redhat.com>
- Don't verify md5sum, size, or timestamp of /var/log/lastlog, /etc/passwd,
  or /etc/group.
