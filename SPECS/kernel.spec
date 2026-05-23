# All Global changes to build and install go here.
# Per the below section about __spec_install_pre, any rpm
# environment changes that affect %%install need to go
# here before the %%install macro is pre-built.

# Disable frame pointers
%undefine _include_frame_pointers

# Disable LTO in userspace packages.
%global _lto_cflags %{nil}

# Option to enable compiling with clang instead of gcc.
%bcond_with toolchain_clang

%if %{with toolchain_clang}
%global toolchain clang
%endif

# Compile the kernel with LTO (only supported when building with clang).
%bcond_with clang_lto

%if %{with clang_lto} && %{without toolchain_clang}
{error:clang_lto requires --with toolchain_clang}
%endif

# RPM macros strip everything in BUILDROOT, either with __strip
# or find-debuginfo.sh. Make use of __spec_install_post override
# and save/restore binaries we want to package as unstripped.
%define buildroot_unstripped %{_builddir}/root_unstripped
%define buildroot_save_unstripped() \
(cd %{buildroot}; cp -rav --parents -t %{buildroot_unstripped}/ %1 || true) \
%{nil}
%define __restore_unstripped_root_post \
    echo "Restoring unstripped artefacts %{buildroot_unstripped} -> %{buildroot}" \
    cp -rav %{buildroot_unstripped}/. %{buildroot}/ \
%{nil}

# The kernel's %%install section is special
# Normally the %%install section starts by cleaning up the BUILD_ROOT
# like so:
#
# %%__spec_install_pre %%{___build_pre}\
#     [ "$RPM_BUILD_ROOT" != "/" ] && rm -rf "${RPM_BUILD_ROOT}"\
#     mkdir -p `dirname "$RPM_BUILD_ROOT"`\
#     mkdir "$RPM_BUILD_ROOT"\
# %%{nil}
#
# But because of kernel variants, the %%build section, specifically
# BuildKernel(), moves each variant to its final destination as the
# variant is built.  This violates the expectation of the %%install
# section.  As a result we snapshot the current env variables and
# purposely leave out the removal section.  All global wide changes
# should be added above this line otherwise the %%install section
# will not see them.
%global __spec_install_pre %{___build_pre}

# Replace '-' with '_' where needed so that variants can use '-' in
# their name.
%define uname_suffix() %{lua:
	local flavour = rpm.expand('%{?1:+%{1}}')
	flavour = flavour:gsub('-', '_')
	if flavour ~= '' then
		print(flavour)
	end
}

# This returns the main kernel tied to a debug variant. For example,
# kernel-debug is the debug version of kernel, so we return an empty
# string. However, kernel-64k-debug is the debug version of kernel-64k,
# in this case we need to return "64k", and so on. This is used in
# macros below where we need this for some uname based requires.
%define uname_variant() %{lua:
	local flavour = rpm.expand('%{?1:%{1}}')
	_, _, main, sub = flavour:find("(%w+)-(.*)")
	if main then
		print("+" .. main)
	end
}


# At the time of this writing (2019-03), RHEL8 packages use w2.xzdio
# compression for rpms (xz, level 2).
# Kernel has several large (hundreds of mbytes) rpms, they take ~5 mins
# to compress by single-threaded xz. Switch to threaded compression,
# and from level 2 to 3 to keep compressed sizes close to "w2" results.
#
# NB: if default compression in /usr/lib/rpm/redhat/macros ever changes,
# this one might need tweaking (e.g. if default changes to w3.xzdio,
# change below to w4T.xzdio):
#
# This is disabled on i686 as it triggers oom errors

%ifnarch i686
%define _binary_payload w3T.xzdio
%endif

Summary: The Linux kernel
%if 0%{?fedora}
%define secure_boot_arch x86_64
%else
%define secure_boot_arch x86_64 aarch64 s390x ppc64le
%endif

# Signing for secure boot authentication
%ifarch %{secure_boot_arch}
%global signkernel 1
%else
%global signkernel 0
%endif

# Sign modules on all arches
%global signmodules 1

# Compress modules only for architectures that build modules
%ifarch noarch
%global zipmodules 0
%else
%global zipmodules 1
%endif

# Default compression algorithm
%global compression xz
%global compression_flags --compress
%global compext xz
%if %{zipmodules}
%global zipsed -e 's/\.ko$/\.ko.%compext/'
%endif

%if 0%{?fedora}
%define primary_target fedora
%else
%define primary_target rhel
%endif

#
# genspec.sh variables
#

# kernel package name
%global package_name kernel
%global gemini 0
# Include Fedora files
%global include_fedora 1
# Include RHEL files
%global include_rhel 1
# Include RT files
%global include_rt 1
# Provide Patchlist.changelog file
%global patchlist_changelog 1
# Set released_kernel to 1 when the upstream source tarball contains a
#  kernel release. (This includes prepatch or "rc" releases.)
# Set released_kernel to 0 when the upstream source tarball contains an
#  unreleased kernel development snapshot.
%global released_kernel 1
# Set debugbuildsenabled to 1 to build separate base and debug kernels
#  (on supported architectures). The kernel-debug-* subpackages will
#  contain the debug kernel.
# Set debugbuildsenabled to 0 to not build a separate debug kernel, but
#  to build the base kernel using the debug configuration. (Specifying
#  the --with-release option overrides this setting.)
%define debugbuildsenabled 1
%define buildid .eswin
%define specrpmversion 6.6.141
%define specversion 6.6.141
%define patchversion 6.6
%define pkgrelease 200
%define kversion 6
%define tarfile_release 6.6.141
# This is needed to do merge window version magic
%define patchlevel 6
# This allows pkg_release to have configurable %%{?dist} tag
%define specrelease 200%{?buildid}%{?dist}
# This defines the kabi tarball version
%define kabiversion 6.6.141

# If this variable is set to 1, a bpf selftests build failure will cause a
# fatal kernel package build error
%define selftests_must_build 0

#
# End of genspec.sh variables
#

%define pkg_release %{specrelease}

# libexec dir is not used by the linker, so the shared object there
# should not be exported to RPM provides
%global __provides_exclude_from ^%{_libexecdir}/kselftests

# The following build options are (mostly) enabled by default, but may become
# enabled/disabled by later architecture-specific checks.
# Where disabled by default, they can be enabled by using --with <opt> in the
# rpmbuild command, or by forcing these values to 1.
# Where enabled by default, they can be disabled by using --without <opt> in
# the rpmbuild command, or by forcing these values to 0.
#
# standard kernel
%define with_up        %{?_without_up:        0} %{?!_without_up:        1}
# build the base variants
%define with_base      %{?_without_base:      0} %{?!_without_base:      1}
# build also debug variants
%define with_debug     %{?_without_debug:     0} %{?!_without_debug:     1}
# kernel-zfcpdump (s390 specific kernel for zfcpdump)
%define with_zfcpdump  %{?_without_zfcpdump:  0} %{?!_without_zfcpdump:  1}
# kernel-16k (aarch64 kernel with 16K page_size)
%define with_arm64_16k %{?_with_arm64_16k:    1} %{?!_with_arm64_16k:    0}
# kernel-64k (aarch64 kernel with 64K page_size)
%define with_arm64_64k %{?_without_arm64_64k: 0} %{?!_without_arm64_64k: 1}
# kernel-rt (x86_64 and aarch64 only PREEMPT_RT enabled kernel)
%define with_realtime  %{?_with_realtime:     1} %{?!_with_realtime:     0}

# Supported variants
#            with_base with_debug    with_gcov
# up         X         X             X
# zfcpdump   X                       X
# arm64_16k  X         X             X
# arm64_64k  X         X             X
# realtime   X         X             X

# kernel-doc
%define with_doc       %{?_without_doc:       0} %{?!_without_doc:       1}
# kernel-headers
%define with_headers   %{?_without_headers:   0} %{?!_without_headers:   1}
%define with_cross_headers   %{?_without_cross_headers:   0} %{?!_without_cross_headers:   1}
# perf
%define with_perf      %{?_without_perf:      0} %{?!_without_perf:      1}
# tools
%define with_tools     %{?_without_tools:     0} %{?!_without_tools:     1}
# bpf tool
%define with_bpftool   %{?_without_bpftool:   0} %{?!_without_bpftool:   1}
# kernel-debuginfo
%define with_debuginfo %{?_without_debuginfo: 0} %{?!_without_debuginfo: 1}
# kernel-abi-stablelists
%define with_kernel_abi_stablelists %{?_without_kernel_abi_stablelists: 0} %{?!_without_kernel_abi_stablelists: 1}
# internal samples and selftests
%define with_selftests %{?_without_selftests: 0} %{?!_without_selftests: 1}
#
# Additional options for user-friendly one-off kernel building:
#
# Only build the base kernel (--with baseonly):
%define with_baseonly  %{?_with_baseonly:     1} %{?!_with_baseonly:     0}
# Only build the debug variants (--with dbgonly):
%define with_dbgonly   %{?_with_dbgonly:      1} %{?!_with_dbgonly:      0}
# Only build the realtime kernel (--with rtonly):
%define with_rtonly    %{?_with_rtonly:       1} %{?!_with_rtonly:       0}
# Control whether we perform a compat. check against published ABI.
%define with_kabichk   %{?_without_kabichk:   0} %{?!_without_kabichk:   1}
# Temporarily disable kabi checks until RC.
%define with_kabichk 0
# Control whether we perform a compat. check against DUP ABI.
%define with_kabidupchk %{?_with_kabidupchk:  1} %{?!_with_kabidupchk:   0}
#
# Control whether to run an extensive DWARF based kABI check.
# Note that this option needs to have baseline setup in SOURCE300.
%define with_kabidwchk %{?_without_kabidwchk: 0} %{?!_without_kabidwchk: 1}
%define with_kabidw_base %{?_with_kabidw_base: 1} %{?!_with_kabidw_base: 0}
#
# Control whether to install the vdso directories.
%define with_vdso_install %{?_without_vdso_install: 0} %{?!_without_vdso_install: 1}
#
# should we do C=1 builds with sparse
%define with_sparse    %{?_with_sparse:       1} %{?!_with_sparse:       0}
#
# Cross compile requested?
%define with_cross    %{?_with_cross:         1} %{?!_with_cross:        0}
#
# build a release kernel on rawhide
%define with_release   %{?_with_release:      1} %{?!_with_release:      0}

# verbose build, i.e. no silent rules and V=1
%define with_verbose %{?_with_verbose:        1} %{?!_with_verbose:      0}

#
# check for mismatched config options
%define with_configchecks %{?_without_configchecks:        0} %{?!_without_configchecks:        1}

#
# gcov support
%define with_gcov %{?_with_gcov:1}%{?!_with_gcov:0}

#
# ipa_clone support
%define with_ipaclones %{?_without_ipaclones: 0} %{?!_without_ipaclones: 1}

# Want to build a vanilla kernel build without any non-upstream patches?
%define with_vanilla %{?_with_vanilla: 1} %{?!_with_vanilla: 0}

%ifarch x86_64
%define with_efiuki %{?_without_efiuki: 0} %{?!_without_efiuki: 1}
%else
%define with_efiuki 0
%endif

%if 0%{?fedora}
# Kernel headers are being split out into a separate package
%define with_headers 0
%define with_cross_headers 0
# no ipa_clone for now
%define with_ipaclones 0
# no stablelist
%define with_kernel_abi_stablelists 0
# Fedora builds these separately
%define with_perf 0
%define with_tools 0
%define with_bpftool 0
# No realtime fedora variants
%define with_realtime 0
%define with_arm64_64k 0
%endif

%if %{with_verbose}
%define make_opts V=1
%else
%define make_opts -s
%endif

%if %{with toolchain_clang}
%ifarch s390x ppc64le
%global llvm_ias 0
%else
%global llvm_ias 1
%endif
%global clang_make_opts HOSTCC=clang CC=clang LLVM_IAS=%{llvm_ias}
%if %{with clang_lto}
%global clang_make_opts %{clang_make_opts} LD=ld.lld HOSTLD=ld.lld AR=llvm-ar NM=llvm-nm HOSTAR=llvm-ar HOSTNM=llvm-nm
%endif
%global make_opts %{make_opts} %{clang_make_opts}
# clang does not support the -fdump-ipa-clones option
%global with_ipaclones 0
%endif

# turn off debug kernel and kabichk for gcov builds
%if %{with_gcov}
%define with_debug 0
%define with_kabichk 0
%define with_kabidupchk 0
%define with_kabidwchk 0
%define with_kabidw_base 0
%define with_kernel_abi_stablelists 0
%endif

# turn off kABI DWARF-based check if we're generating the base dataset
%if %{with_kabidw_base}
%define with_kabidwchk 0
%endif

# kpatch_kcflags are extra compiler flags applied to base kernel
# -fdump-ipa-clones is enabled only for base kernels on selected arches
%if %{with_ipaclones}
%ifarch x86_64 ppc64le
%define kpatch_kcflags -fdump-ipa-clones
%else
%define with_ipaclones 0
%endif
%endif

%define make_target bzImage
%define image_install_path boot

%define KVERREL %{specversion}-%{release}.%{_target_cpu}
%define KVERREL_RE %(echo %KVERREL | sed 's/+/[+]/g')
%define hdrarch %_target_cpu
%define asmarch %_target_cpu

%if 0%{!?nopatches:1}
%define nopatches 0
%endif

%if %{with_vanilla}
%define nopatches 1
%endif

%if %{with_release}
%define debugbuildsenabled 1
%endif

%if !%{with_debuginfo}
%define _enable_debug_packages 0
%endif
%define debuginfodir /usr/lib/debug
# Needed because we override almost everything involving build-ids
# and debuginfo generation. Currently we rely on the old alldebug setting.
%global _build_id_links alldebug

# if requested, only build base kernel
%if %{with_baseonly}
%define with_debug 0
%define with_realtime 0
%define with_vdso_install 0
%define with_perf 0
%define with_tools 0
%define with_bpftool 0
%define with_kernel_abi_stablelists 0
%define with_selftests 0
%define with_cross 0
%define with_cross_headers 0
%define with_ipaclones 0
%endif

# if requested, only build debug kernel
%if %{with_dbgonly}
%define with_base 0
%define with_vdso_install 0
%define with_perf 0
%define with_tools 0
%define with_bpftool 0
%define with_kernel_abi_stablelists 0
%define with_selftests 0
%define with_ipaclones 0
%endif

# if requested, only build realtime kernel
%if %{with_rtonly}
%define with_realtime 1
%define with_up 0
%define with_debug 0
%define with_debuginfo 0
%define with_vdso_install 0
%define with_perf 0
%define with_tools 0
%define with_bpftool 0
%define with_kernel_abi_stablelists 0
%define with_selftests 0
%define with_cross 0
%define with_cross_headers 0
%define with_ipaclones 0
%define with_headers 0
%define with_efiuki 0
%define with_zfcpdump 0
%define with_arm64_16k 0
%define with_arm64_64k 0
%endif

# RT kernel is only built on x86_64 and aarch64
%ifnarch x86_64 aarch64
%define with_realtime 0
%endif

# turn off kABI DUP check and DWARF-based check if kABI check is disabled
%if !%{with_kabichk}
%define with_kabidupchk 0
%define with_kabidwchk 0
%endif

%if %{with_vdso_install}
%define use_vdso 1
%endif

# selftests require bpftool to be built.  If bpftools is disabled, then disable selftests
%if %{with_bpftool} == 0
%define with_selftests 0
%endif

%ifnarch noarch
%define with_kernel_abi_stablelists 0
%endif

# Overrides for generic default options

# only package docs noarch
%ifnarch noarch
%define with_doc 0
%define doc_build_fail true
%endif

%if 0%{?fedora}
# don't do debug builds on anything but aarch64 and x86_64
%ifnarch aarch64 x86_64
%define with_debug 0
%endif
%endif

%define all_configs %{name}-%{specrpmversion}-*.config

# don't build noarch kernels or headers (duh)
%ifarch noarch
%define with_up 0
%define with_realtime 0
%define with_headers 0
%define with_cross_headers 0
%define with_tools 0
%define with_perf 0
%define with_bpftool 0
%define with_selftests 0
%define with_debug 0
%endif

# sparse blows up on ppc
%ifnarch ppc64le
%define with_sparse 0
%endif

# zfcpdump mechanism is s390 only
%ifnarch s390x
%define with_zfcpdump 0
%endif

# 16k and 64k variants only for aarch64
%ifnarch aarch64
%define with_arm64_16k 0
%define with_arm64_64k 0
%endif

%if 0%{?fedora}
# This is not for Fedora
%define with_zfcpdump 0
%endif

# Per-arch tweaks

%ifarch i686
%define asmarch x86
%define hdrarch i386
%define kernel_image arch/x86/boot/bzImage
%endif

%ifarch x86_64
%define asmarch x86
%define kernel_image arch/x86/boot/bzImage
%endif

%ifarch ppc64le
%define asmarch powerpc
%define hdrarch powerpc
%define make_target vmlinux
%define kernel_image vmlinux
%define kernel_image_elf 1
%define use_vdso 0
%endif

%ifarch s390x
%define asmarch s390
%define hdrarch s390
%define kernel_image arch/s390/boot/bzImage
%define vmlinux_decompressor arch/s390/boot/vmlinux
%endif

%ifarch aarch64
%define asmarch arm64
%define hdrarch arm64
%define make_target vmlinuz.efi
%define kernel_image arch/arm64/boot/vmlinuz.efi
%endif

%ifarch riscv64
%define asmarch riscv
%define hdrarch riscv
%define make_target vmlinuz.efi
%define kernel_image arch/riscv/boot/vmlinuz.efi
%endif

# Should make listnewconfig fail if there's config options
# printed out?
%if %{nopatches}
%define with_configchecks 0
%endif

# To temporarily exclude an architecture from being built, add it to
# %%nobuildarches. Do _NOT_ use the ExclusiveArch: line, because if we
# don't build kernel-headers then the new build system will no longer let
# us use the previous build of that package -- it'll just be completely AWOL.
# Which is a BadThing(tm).

# We only build kernel-headers on the following...
%if 0%{?fedora}
%define nobuildarches i386
%else
%define nobuildarches i386 i686
%endif

%ifarch %nobuildarches
# disable BuildKernel commands
%define with_up 0
%define with_debug 0
%define with_zfcpdump 0
%define with_arm64_16k 0
%define with_arm64_64k 0
%define with_realtime 0

%define with_debuginfo 0
%define with_perf 0
%define with_tools 0
%define with_bpftool 0
%define with_selftests 0
%define _enable_debug_packages 0
%endif

# Architectures we build tools/cpupower on
%if 0%{?fedora}
%define cpupowerarchs %{ix86} x86_64 ppc64le aarch64
%else
%define cpupowerarchs i686 x86_64 ppc64le aarch64
%endif

%if 0%{?use_vdso}
%define _use_vdso 1
%else
%define _use_vdso 0
%endif

# If build of debug packages is disabled, we need to know if we want to create
# meta debug packages or not, after we define with_debug for all specific cases
# above. So this must be at the end here, after all cases of with_debug or not.
%define with_debug_meta 0
%if !%{debugbuildsenabled}
%if %{with_debug}
%define with_debug_meta 1
%endif
%define with_debug 0
%endif

# short-hand for "are we building base/non-debug variants of ...?"
%if %{with_up} && %{with_base}
%define with_up_base 1
%else
%define with_up_base 0
%endif
%if %{with_realtime} && %{with_base}
%define with_realtime_base 1
%else
%define with_realtime_base 0
%endif
%if %{with_arm64_16k} && %{with_base}
%define with_arm64_16k_base 1
%else
%define with_arm64_16k_base 0
%endif
%if %{with_arm64_64k} && %{with_base}
%define with_arm64_64k_base 1
%else
%define with_arm64_64k_base 0
%endif

#
# Packages that need to be installed before the kernel is, because the %%post
# scripts use them.
#
%define kernel_prereq  coreutils, systemd >= 203-2, /usr/bin/kernel-install
%define initrd_prereq  dracut >= 027


Name: %{package_name}
License: ((GPL-2.0-only WITH Linux-syscall-note) OR BSD-2-Clause) AND ((GPL-2.0-only WITH Linux-syscall-note) OR BSD-3-Clause) AND ((GPL-2.0-only WITH Linux-syscall-note) OR CDDL-1.0) AND ((GPL-2.0-only WITH Linux-syscall-note) OR Linux-OpenIB) AND ((GPL-2.0-only WITH Linux-syscall-note) OR MIT) AND ((GPL-2.0-or-later WITH Linux-syscall-note) OR BSD-3-Clause) AND ((GPL-2.0-or-later WITH Linux-syscall-note) OR MIT) AND BSD-2-Clause AND BSD-3-Clause AND BSD-3-Clause-Clear AND GFDL-1.1-no-invariants-or-later AND GPL-1.0-or-later AND (GPL-1.0-or-later OR BSD-3-Clause) AND (GPL-1.0-or-later WITH Linux-syscall-note) AND GPL-2.0-only AND (GPL-2.0-only OR Apache-2.0) AND (GPL-2.0-only OR BSD-2-Clause) AND (GPL-2.0-only OR BSD-3-Clause) AND (GPL-2.0-only OR CDDL-1.0) AND (GPL-2.0-only OR GFDL-1.1-no-invariants-or-later) AND (GPL-2.0-only OR GFDL-1.2-no-invariants-only) AND (GPL-2.0-only WITH Linux-syscall-note) AND GPL-2.0-or-later AND (GPL-2.0-or-later OR BSD-2-Clause) AND (GPL-2.0-or-later OR BSD-3-Clause) AND (GPL-2.0-or-later OR CC-BY-4.0) AND (GPL-2.0-or-later WITH GCC-exception-2.0) AND (GPL-2.0-or-later WITH Linux-syscall-note) AND ISC AND LGPL-2.0-or-later AND (LGPL-2.0-or-later OR BSD-2-Clause) AND (LGPL-2.0-or-later WITH Linux-syscall-note) AND LGPL-2.1-only AND (LGPL-2.1-only OR BSD-2-Clause) AND (LGPL-2.1-only WITH Linux-syscall-note) AND LGPL-2.1-or-later AND (LGPL-2.1-or-later WITH Linux-syscall-note) AND (Linux-OpenIB OR GPL-2.0-only) AND (Linux-OpenIB OR GPL-2.0-only OR BSD-2-Clause) AND Linux-man-pages-copyleft AND MIT AND (MIT OR Apache-2.0) AND (MIT OR GPL-2.0-only) AND (MIT OR GPL-2.0-or-later) AND (MIT OR LGPL-2.1-only) AND (MPL-1.1 OR GPL-2.0-only) AND (X11 OR GPL-2.0-only) AND (X11 OR GPL-2.0-or-later) AND Zlib AND (copyleft-next-0.3.1 OR GPL-2.0-or-later)
URL: https://www.kernel.org/
Version: %{specrpmversion}
Release: %{pkg_release}
# DO NOT CHANGE THE 'ExclusiveArch' LINE TO TEMPORARILY EXCLUDE AN ARCHITECTURE BUILD.
# SET %%nobuildarches (ABOVE) INSTEAD
%if 0%{?fedora}
ExclusiveArch: noarch x86_64 s390x aarch64 ppc64le riscv64
%else
ExclusiveArch: noarch i386 i686 x86_64 s390x aarch64 ppc64le
%endif
ExclusiveOS: Linux
%ifnarch %{nobuildarches}
Requires: kernel-core-uname-r = %{KVERREL}
Requires: kernel-modules-uname-r = %{KVERREL}
Requires: kernel-modules-core-uname-r = %{KVERREL}
Provides: installonlypkg(kernel)
%endif


#
# List the packages used during the kernel build
#
BuildRequires: kmod, bash, coreutils, tar, git-core, which
BuildRequires: bzip2, xz, findutils, m4, perl-interpreter, perl-Carp, perl-devel, perl-generators, make, diffutils, gawk, %compression
BuildRequires: gcc, binutils, redhat-rpm-config, hmaccalc, bison, flex, gcc-c++
BuildRequires: net-tools, hostname, bc, elfutils-devel
BuildRequires: dwarves
BuildRequires: python3-devel
BuildRequires: kernel-rpm-macros
# glibc-static is required for a consistent build environment (specifically
# CONFIG_CC_CAN_LINK_STATIC=y).
BuildRequires: glibc-static
%ifnarch %{nobuildarches} noarch
BuildRequires: bpftool
%endif
%if %{with_headers}
BuildRequires: rsync
%endif
%if %{with_doc}
BuildRequires: xmlto, asciidoc, python3-sphinx, python3-sphinx_rtd_theme
%endif
%if %{with_sparse}
BuildRequires: sparse
%endif
%if %{with_perf}
BuildRequires: zlib-devel binutils-devel newt-devel perl(ExtUtils::Embed) bison flex xz-devel
BuildRequires: audit-libs-devel python3-setuptools
BuildRequires: java-devel
BuildRequires: libbpf-devel >= 0.6.0-1
BuildRequires: libbabeltrace-devel
BuildRequires: libtraceevent-devel
%ifnarch s390x
BuildRequires: numactl-devel
%endif
%ifarch aarch64
BuildRequires: opencsd-devel >= 1.0.0
%endif
%endif
%if %{with_tools}
BuildRequires: python3-docutils
BuildRequires: gettext ncurses-devel
BuildRequires: libcap-devel libcap-ng-devel
BuildRequires: libtracefs-devel
%ifnarch s390x
BuildRequires: pciutils-devel
%endif
%ifarch i686 x86_64
BuildRequires: libnl3-devel
%endif
%endif
%if %{with_tools} || %{signmodules} || %{signkernel}
BuildRequires: openssl-devel openssl-devel-engine
%endif
%if %{with_bpftool}
BuildRequires: python3-docutils
BuildRequires: zlib-devel binutils-devel
%endif
%if %{with_selftests}
BuildRequires: clang llvm-devel fuse-devel
BuildRequires: libcap-devel libcap-ng-devel rsync libmnl-devel
BuildRequires: numactl-devel
%endif
BuildConflicts: rhbuildsys(DiskFree) < 500Mb
%if %{with_debuginfo}
BuildRequires: rpm-build, elfutils
BuildConflicts: rpm < 4.13.0.1-19
BuildConflicts: dwarves < 1.13
# Most of these should be enabled after more investigation
%undefine _include_minidebuginfo
%undefine _find_debuginfo_dwz_opts
%undefine _unique_build_ids
%undefine _unique_debug_names
%undefine _unique_debug_srcs
%undefine _debugsource_packages
%undefine _debuginfo_subpackages

# Remove -q option below to provide 'extracting debug info' messages
%global _find_debuginfo_opts -r -q

%global _missing_build_ids_terminate_build 1
%global _no_recompute_build_ids 1
%endif
%if %{with_kabidwchk} || %{with_kabidw_base}
BuildRequires: kabi-dw
%endif

%if %{signkernel}%{signmodules}
BuildRequires: openssl
%if %{signkernel}
# ELN uses Fedora signing process, so exclude
%if 0%{?rhel}%{?centos} && !0%{?eln}
BuildRequires: system-sb-certs
%endif
%ifarch x86_64 aarch64
BuildRequires: nss-tools
BuildRequires: pesign >= 0.10-4
%endif
%endif
%endif

%if %{with_cross}
BuildRequires: binutils-%{_build_arch}-linux-gnu, gcc-%{_build_arch}-linux-gnu
%define cross_opts CROSS_COMPILE=%{_build_arch}-linux-gnu-
%define __strip %{_build_arch}-linux-gnu-strip
%endif

# These below are required to build man pages
%if %{with_perf}
BuildRequires: xmlto
%endif
%if %{with_perf} || %{with_tools}
BuildRequires: asciidoc
%endif

%if %{with toolchain_clang}
BuildRequires: clang
%endif

%if %{with clang_lto}
BuildRequires: llvm
BuildRequires: lld
%endif

%if %{with_efiuki}
BuildRequires: dracut
# For dracut UEFI uki binaries
BuildRequires: binutils
# For the initrd
BuildRequires: lvm2
BuildRequires: systemd-boot-unsigned
# For systemd-stub and systemd-pcrphase
BuildRequires: systemd-udev
# For TPM operations in UKI initramfs
BuildRequires: tpm2-tools
%endif

# Because this is the kernel, it's hard to get a single upstream URL
# to represent the base without needing to do a bunch of patching. This
# tarball is generated from a src-git tree. If you want to see the
# exact git commit you can run
#
# xzcat -qq ${TARBALL} | git get-tar-commit-id
Source0: linux-%{tarfile_release}.tar.xz

Source1: Makefile.rhelver


# Name of the packaged file containing signing key
%ifarch ppc64le
%define signing_key_filename kernel-signing-ppc.cer
%endif
%ifarch s390x
%define signing_key_filename kernel-signing-s390.cer
%endif

%if %{?released_kernel}

Source10: redhatsecurebootca5.cer
Source11: redhatsecurebootca1.cer
Source12: redhatsecureboot501.cer
Source13: redhatsecureboot301.cer
Source14: secureboot_s390.cer
Source15: secureboot_ppc.cer

%define secureboot_ca_1 %{SOURCE10}
%define secureboot_ca_0 %{SOURCE11}
%ifarch x86_64 aarch64
%define secureboot_key_1 %{SOURCE12}
%define pesign_name_1 redhatsecureboot501
%define secureboot_key_0 %{SOURCE13}
%define pesign_name_0 redhatsecureboot301
%endif
%ifarch s390x
%define secureboot_key_0 %{SOURCE14}
%define pesign_name_0 redhatsecureboot302
%endif
%ifarch ppc64le
%define secureboot_key_0 %{SOURCE15}
%define pesign_name_0 redhatsecureboot303
%endif

# released_kernel
%else

Source10: redhatsecurebootca4.cer
Source11: redhatsecurebootca2.cer
Source12: redhatsecureboot401.cer
Source13: redhatsecureboot003.cer

%define secureboot_ca_1 %{SOURCE10}
%define secureboot_ca_0 %{SOURCE11}
%define secureboot_key_1 %{SOURCE12}
%define pesign_name_1 redhatsecureboot401
%define secureboot_key_0 %{SOURCE13}
%define pesign_name_0 redhatsecureboot003

# released_kernel
%endif

Source20: mod-denylist.sh
Source21: mod-sign.sh

%define modsign_cmd %{SOURCE21}

%if 0%{?include_rhel}
Source23: x509.genkey.rhel

Source26: mod-extra.list.rhel

Source34: filter-x86_64.sh.rhel
Source35: filter-aarch64.sh.rhel
Source36: filter-ppc64le.sh.rhel
Source37: filter-s390x.sh.rhel
Source38: filter-modules.sh.rhel

Source41: x509.genkey.centos

%endif

%if 0%{?include_fedora}
Source50: x509.genkey.fedora
Source51: mod-extra.list.fedora

Source700: %{name}-riscv64-fedora.config
Source701: %{name}-riscv64-debug-fedora.config

Source62: filter-x86_64.sh.fedora
Source63: filter-aarch64.sh.fedora
Source64: filter-ppc64le.sh.fedora
Source65: filter-s390x.sh.fedora
Source66: filter-modules.sh.fedora
Source702: filter-riscv64.sh.fedora
%endif

Source70: partial-kgcov-snip.config
Source71: partial-kgcov-debug-snip.config
Source72: partial-clang-snip.config
Source73: partial-clang-debug-snip.config
Source74: partial-clang_lto-x86_64-snip.config
Source75: partial-clang_lto-x86_64-debug-snip.config
Source76: partial-clang_lto-aarch64-snip.config
Source77: partial-clang_lto-aarch64-debug-snip.config
Source80: generate_all_configs.sh
Source81: process_configs.sh

Source82: update_scripts.sh

Source84: mod-internal.list
Source85: mod-partner.list

Source86: dracut-virt.conf

Source87: flavors

Source100: rheldup3.x509
Source101: rhelkpatch1.x509

Source200: check-kabi

Source201: Module.kabi_aarch64
Source202: Module.kabi_ppc64le
Source203: Module.kabi_s390x
Source204: Module.kabi_x86_64
Source205: Module.kabi_riscv64

Source210: Module.kabi_dup_aarch64
Source211: Module.kabi_dup_ppc64le
Source212: Module.kabi_dup_s390x
Source213: Module.kabi_dup_x86_64
Source214: Module.kabi_dup_riscv64

Source300: kernel-abi-stablelists-%{kabiversion}.tar.xz
Source301: kernel-kabi-dw-%{kabiversion}.tar.xz

# RT specific virt module
Source400: mod-kvm.list

%if %{include_rt}
%endif

# Sources for kernel-tools
Source2002: kvm_stat.logrotate

# Some people enjoy building customized kernels from the dist-git in Fedora and
# use this to override configuration options. One day they may all use the
# source tree, but in the mean time we carry this to support the legacy workflow
Source3000: merge.py
Source3001: kernel-local
%if %{patchlist_changelog}
Source3002: Patchlist.changelog
%endif

Source4000: README.rst
Source4001: rpminspect.yaml
Source4002: gating.yaml

## Patches needed for building this package

%if !%{nopatches}

Patch1: patch-%{patchversion}-redhat.patch





Patch10001: 0001-Added-dts-and-defconfig-files-modified-8250_dwlib.c-.patch
Patch10002: 0002-Added-clk-reset-driver.patch
Patch10003: 0003-feat-dma-coherent-noncoherent-Support-dma-coherent-n.patch
Patch10004: 0004-feat-eswin-memory-Added-eswin-memory-related-changes.patch
Patch10005: 0005-feat-SMMU-support-Support-SMMU.patch
Patch10006: 0006-feat-eswin-mailbox-Added-eswin-mailbox-related-chang.patch
Patch10007: 0007-feat-eswin-pinctrl-Added-eswin-pinctrl-related-chang.patch
Patch10008: 0008-feat-Add-support-for-ethernet-driver.patch
Patch10009: 0009-feat-EVB-A2-dts-pcie-Added-EVB-A2-dts.patch
Patch10010: 0010-feat-CMA-Select-CONFIG_CMA-and-CONFIG_DMA_CMA.patch
Patch10011: 0011-feat-bootspi-Add-bootspi-flash-driver.patch
Patch10012: 0012-feat-noc-Add-noc-driver.patch
Patch10013: 0013-feat-Add-VO-support-for-linux-6.6.patch
Patch10014: 0014-feat-Add-emmc-and-sdio-driver.patch
Patch10015: 0015-fix-vo-add-dma-noncoherent-for-video-ouput-device.patch
Patch10016: 0016-feat-support-eswin-dwc3-usb.patch
Patch10017: 0017-feat-support-ddr-ecc-check-and-report.patch
Patch10018: 0018-feat-Porting-eswin-audio-to-6.6-kernel.patch
Patch10019: 0019-feat-support-mpq8785-to-set-npu-voltage.patch
Patch10020: 0020-feat-Add-dma-driver.patch
Patch10021: 0021-feat-Select-emmc-sdio-wireless-drivers-by-default.patch
Patch10022: 0022-feat-spram-Treat-spram-as-part-of-the-sys-memory-spa.patch
Patch10023: 0023-feat-cma-heap-Select-CONFIG_DMABUF_HEAPS_CMA.patch
Patch10024: 0024-feat-sata-driver-to-linux-6.6.patch
Patch10025: 0025-feat-add-support-pac1934-to-get-som-voltage-info.patch
Patch10026: 0026-fix-modify-ina226-addr-and-hold-time.patch
Patch10027: 0027-fix-IOMMU-Add-ARCH_HAS_TEARDOWN_DMA_OPS.patch
Patch10028: 0028-feat-Porting-hdmi-driver-to-linux-6.6.patch
Patch10029: 0029-feat-DRM-Add-DSI-support-for-linux-6.6.patch
Patch10030: 0030-feat-add-fan-rtc-wdt-dw-spi-pwm.patch
Patch10031: 0031-feat-pvt_sensors-driver-to-linux-6.6.patch
Patch10032: 0032-refactor-khandle-dsp-subsys-drv.patch
Patch10033: 0033-fix-modify-fan-control-and-read-fan-speed.patch
Patch10034: 0034-fix-Add-rtc-pcf8573-driver-in-win2030_defconfig.patch
Patch10035: 0035-fix-add-sysfs-in-pac1934-to-set-update-interval.patch
Patch10036: 0036-feat-llc_spram-set-npu-default-freq-to-1.5G.patch
Patch10037: 0037-fix-llc_spram-Removed-linux-version-check.patch
Patch10038: 0038-perf-update-dma-pwm-timer-driver.patch
Patch10039: 0039-fix-dsp-dma-ranges-buf-fix.patch
Patch10040: 0040-refactor-remove-useless-code-in-emmc-sd-driver.patch
Patch10041: 0041-fix-distinguish-built-in-RTC-and-PCF-RTC.patch
Patch10042: 0042-fix-adapt-linux6.6.patch
Patch10043: 0043-fix-delete-useless-audio-code.patch
Patch10044: 0044-fix-add-label-for-all-hwmon.patch
Patch10045: 0045-feat-add-dirver-for-fsub303-to-support-type-c.patch
Patch10046: 0046-chore-es_buddy-Memory-workaround-for-g2d-hardware-pr.patch
Patch10047: 0047-feat-ISP-Add-VI-dev-to-linux-6.6.patch
Patch10048: 0048-fix-add-enable-disable-for-hdcp1x.patch
Patch10049: 0049-fix-optimize-SDHCI-driver.patch
Patch10050: 0050-feat-Support-tca6416-for-csi-reset.patch
Patch10051: 0051-refactor-Implement-pcie-intx-and-pmu-dtsi-config.patch
Patch10052: 0052-fix-modify-LSB-for-mpq8785-to-1mdegress-LSB.patch
Patch10053: 0053-fix-optimize-SDHCI-driver-tuning.patch
Patch10054: 0054-feat-bootspi-flash-support-write-proection.patch
Patch10055: 0055-fix-spi-del-dma.patch
Patch10056: 0056-fix-vo-Fix-cursor-layer-resolution.patch
Patch10057: 0057-fix-Solving-HDMI-driver-compilation-issue.patch
Patch10058: 0058-feat-add-hifive-premier-550-dts.patch
Patch10059: 0059-fix-BootSpi-contronller-check-flash-status-register.patch
Patch10060: 0060-feat-dts-add-apply_npu_high_freq-in-dts.patch
Patch10061: 0061-fix-add-audio-sound-card-name.patch
Patch10062: 0062-fix-set-npu-default-freq-to-1.5G.patch
Patch10063: 0063-fix-delete-extra-print.patch
Patch10064: 0064-fix-support-power-managemnt.patch
Patch10065: 0065-fix-es-buddy-add-spin-lock.patch
Patch10066: 0066-fix-Delete-HDCP1.4-authentication-key.patch
Patch10067: 0067-fix-fix-the-issue-of-getting-hub-descriptor-fail.patch
Patch10068: 0068-fix-fix-the-issue-of-USB-3.0-host-halt.patch
Patch10069: 0069-img-gpu-kmd-migrate-from-5.17-to-6.6.patch
Patch10070: 0070-img-gpu-kmd-remove-warning-of-flush_scheduled_work-t.patch
Patch10071: 0071-img-gpu-kmd-update-kernel-api-of-dma_resv.patch
Patch10072: 0072-img-gpu-kmd-update-kernel-api-dma_buf_map-to-iosys_m.patch
Patch10073: 0073-img-gpu-kmd-update-kernel-api-register_shrinker.patch
Patch10074: 0074-img-gpu-kmd-use-arch_sync_dma_for_device-instead-of-.patch
Patch10075: 0075-img-gpu-kmd-fix-vm_flags-setting-issue.patch
Patch10076: 0076-regulator-mpq8785-mpq8785_label-add-label-len-for-np.patch
Patch10077: 0077-chore-dtb_install-in-boot.patch
Patch10078: 0078-feat-enable-h-ext.patch
Patch10079: 0079-ttm-disallow-cached-mapping.patch
Patch10080: 0080-drm-eswin-fbdev-fix-es-fbdev.patch
Patch10081: 0081-configs-remove-CONFIG_LOCALVERSION_AUTO.patch
Patch10082: 0082-configs-enable-initrd.patch
Patch10083: 0083-configs-enable-amd-gpu-driver.patch
Patch10084: 0084-configs-enable-kvm.patch
Patch10085: 0085-configs-enable-hd-audio-pci-support.patch
Patch10086: 0086-config-enable-option-for-docker-podman.patch
Patch10087: 0087-fix-remove-win2030-localversion.patch
Patch10088: 0088-fix-disable-CONFIG_ESWIN_VIRTUAL_DISPLAY.patch
Patch10089: 0089-configs-enable-CONFIG_BINFMT_MISC.patch
Patch10090: 0090-configs-enable-CONFIG_DEBUG_FS.patch
Patch10091: 0091-configs-enable-MEDIA_USB_SUPPORT-MEDIA_PCI_SUPPORT.patch
Patch10092: 0092-fix-eswin-load-kvm-module-failed.patch
Patch10093: 0093-config-enable-some-options-for-the-distribution.patch
Patch10094: 0094-perf-dw-axi-dmac-print.patch
Patch10095: 0095-fix-bootspi-support-power-managemnt.patch
Patch10096: 0096-chore-change-CONFIG_DMATEST-m.patch
Patch10097: 0097-feat-eth-ETH-support-power-management.patch
Patch10098: 0098-feat-npu-drv-support-low-power.patch
Patch10099: 0099-feat-emmc-sd-sdio-sdhci-support-power-management.patch
Patch10100: 0100-feat-vo-OSD-Support-power-management.patch
Patch10101: 0101-refactor-MMZ-vb-and-heap-MMZ-code-moved-in-kernel.patch
Patch10102: 0102-feat-Video-Integrate-Video-driver-into-linux6.6.patch
Patch10103: 0103-refactor-move-es_dev_buf-and-iommu_rsv-into-kernel.patch
Patch10104: 0104-feat-pmdomain-Add-power-domain-framework-support.patch
Patch10105: 0105-feat-DW200-Dw200-Support-power-management.patch
Patch10106: 0106-feat-adapt-g2d-for-the-RPM-framework.patch
Patch10107: 0107-feat-I2s-support-low-power.patch
Patch10108: 0108-feat-PCIe-Controller-support-low-power.patch
Patch10109: 0109-refactor-remove-1.5GHz-1.8GHz-cpu-freq.patch
Patch10110: 0110-refactor-remove-1.5GHz-1.8GHz-cpu-freq-die1.patch
Patch10111: 0111-fix-cpu-pll-enable-cpu-low-power-clk-when-use-it.patch
Patch10112: 0112-feat-HDMI-support-low-power.patch
Patch10113: 0113-feat-linux-6.6-add-npu-dsp-driver.patch
Patch10114: 0114-feat-sd-wifi-support-power-management.patch
Patch10115: 0115-fix-vo-clk-off-after-dc-initialized.patch
Patch10116: 0116-fix-Fix-a-fan-duty-cycle-error.patch
Patch10117: 0117-fix-put-power-on-if-the-interrupt-came.patch
Patch10118: 0118-fix-check-brother-core-event-queue-empty-when-idle.patch
Patch10119: 0119-feat-PCIe-Controller-PM-support-power-on-off.patch
Patch10120: 0120-fix-eth-Add-tbu-power-down-when-clk-off.patch
Patch10121: 0121-refactor-add-eic7700-defconfig-and-adjust-mmz-size.patch
Patch10122: 0122-fix-fix-the-cpu-100-issue-when-wait-FE-idle.patch
Patch10123: 0123-fix-fix-the-issue-of-sd-resuming-fail.patch
Patch10124: 0124-feat-vdec-support-power-managemnt.patch
Patch10125: 0125-feat-VE-VE-support-power-management.patch
Patch10126: 0126-feat-add-cpu-idle-framework-support.patch
Patch10127: 0127-fix-VE-fix-var-name-redefinition.patch
Patch10128: 0128-feat-Add-lpcpu-driver-for-linux-6.6.patch
Patch10129: 0129-fix-fix-some-ep-device-cannot-resume.patch
Patch10130: 0130-fix-use-timer-500ms-to-try-gpu-idle.patch
Patch10131: 0131-fix-fix-regulator-warning-print.patch
Patch10132: 0132-refactor-add-vo-qos-config.patch
Patch10133: 0133-refactor-modify-evb1-dts.patch
Patch10134: 0134-feat-add-lpcpu-eic7700-defconfig-and-dts.patch
Patch10135: 0135-fix-DW200-Fix-generic-pm-crash-issue.patch
Patch10136: 0136-feat-Introduce-system-suspend-support.patch
Patch10137: 0137-fix-DC8K-data-compressed-when-outputting-RGB.patch
Patch10138: 0138-feat-change-idle-defconfig-from-win2030-to-eic7700.patch
Patch10139: 0139-feat-add-single-die-of-7702-dts.patch
Patch10140: 0140-fix-when-write-protection-config-do-runtime-resume.patch
Patch10141: 0141-fix-signal-to-wait-the-gpu-idle.patch
Patch10142: 0142-feat-Deselect-CONFIG_PM.patch
Patch10143: 0143-feat-remove-nonret-cpu-idle-state.patch
Patch10144: 0144-Revert-Merge-branch-win2030-dev-into-release-730.patch
Patch10145: 0145-feat-Deselect-CONFIG_CPU_IDLE.patch
Patch10146: 0146-refactor-uniform-naming-of-hifive-premier-p550.patch
Patch10147: 0147-feat-KASAN-warnning-bootspi-region-protection.patch
Patch10148: 0148-feat-dsi-support-set-bus-format.patch
Patch10149: 0149-fix-AO-case-failed.patch
Patch10150: 0150-fix-kasan-for-vc-driver.patch
Patch10151: 0151-fix-set-i2s0-io-func-to-GPIO.patch
Patch10152: 0152-fix-enc-opt-log-in-enc-driver.patch
Patch10153: 0153-fix-noc-fix-kmemleak-warning.patch
Patch10154: 0154-fix-chang-the-delayline-of-sdio0.patch
Patch10155: 0155-fix-add-i2c-hold-time-for-aon-i2c.patch
Patch10156: 0156-fix-enc-fix-hang-issue-of-ve-roi.patch
Patch10157: 0157-Merge-patch-series-membarrier-riscv-Core-serializing.patch
Patch10158: 0158-symbol-gpl-export-pud_offset-p4d_offset-symbol.patch
Patch10159: 0159-fix-pwm-eswin-Rename-pwm_apply_state-to-pwm_apply_mi.patch
Patch10160: 0160-riscv-Add-support-for-kernel-mode-FPU.patch
Patch10161: 0161-riscv-Factor-out-riscv-march-y-to-a-separate-Makefil.patch
Patch10162: 0162-drm-amd-display-Support-DRM_AMD_DC_FP-on-RISC-V.patch
Patch10163: 0163-feat-add-eic7700_dbg_defconfig.patch
Patch10164: 0164-feat-Disable-CONFIG_PM.patch
Patch10165: 0165-fix-check_mc_cmdbuf_irq.patch
Patch10166: 0166-fix-Update-the-NPU-DSP-driver-code.patch
Patch10167: 0167-feat-Open-the-NPU-DSP-driver-module.patch
Patch10168: 0168-style-harmonize-device-tree.patch
Patch10169: 0169-feat-npu-drv-need-add-autoload.patch
Patch10170: 0170-feat-Support-mmz-partition-resize.patch
Patch10171: 0171-fix-Synchronize-configuration-from-eic7700_defconfig.patch
Patch10172: 0172-chore-Remove-redundant-log.patch
Patch10173: 0173-chore-Reduce-print-in-mmz_vb.patch
Patch10174: 0174-to-je-disable-je-timeout-check.patch
Patch10175: 0175-feat-add-cpu-volatge-adjust.patch
Patch10176: 0176-feat-merge-DSP-DSP-NPU-SDK-driver-to-linux.patch
Patch10177: 0177-feat-support-bluetooth.patch
Patch10178: 0178-feat-add-trylock-for-npu-ioctl-Changelogs-add-tryloc.patch
Patch10179: 0179-fix-HDMI-audio-only-supports-playback.patch
Patch10180: 0180-feat-Loud-sound-occurs-for-debian-start-for-linux.patch
Patch10181: 0181-fix-dsp-driver-need-cancel-scheduled-work.patch
Patch10182: 0182-feat-fix-clock-pmic-noc-init-initialization-order.patch
Patch10183: 0183-fix-Correct-word-errors-remove-unused-define.patch
Patch10184: 0184-fix-Resolve-DSP-SMMU-error.patch
Patch10185: 0185-fix-CPU-run-1.6GHz-without-voltage-boost-if-allowed.patch
Patch10186: 0186-feat-decode-with-user-space-buffer.patch
Patch10187: 0187-feat-NPU-DSP-drivers-shouldn-t-load-on-failure.patch
Patch10188: 0188-fix-feature-pm-compiliation.patch
Patch10189: 0189-fix-sdk-mc-linstener-thread-cannot-exit.patch
Patch10190: 0190-feat-NPU-DSP-driver-port.patch
Patch10191: 0191-fix-Resolve-the-i2s-driver-crash-issue.patch
Patch10192: 0192-refactor-move-the-cipher-driver-source-code-in-to-ke.patch
Patch10193: 0193-fix-je-access-error-occurred-when-je-stable-test.patch
Patch10194: 0194-fix-The-wrong-dev-id-was-used-for-vcmd-release.patch
Patch10195: 0195-feat-support-IPA-thermal-control.patch
Patch10196: 0196-fix-fix-sata-reset.patch
Patch10197: 0197-sync-drm-support-debugfs-control-virtual.patch
Patch10198: 0198-fix-Solving-hdmi-display-compatibility-issues.patch
Patch10199: 0199-fix-DSP-NPU-driver-code-compliance.patch
Patch10200: 0200-feat-add-license-description.patch
Patch10201: 0201-feat-NOC-driver-adapt-to-bandwidth-test.patch
Patch10202: 0202-feat-dsp-drv-use-dsp-pool-for-flat-mem.patch
Patch10203: 0203-feat-recover-volume-to-6dB-for-debian.patch
Patch10204: 0204-fix-resolve-HDMI-hot-plug-compatibility-issues.patch
Patch10205: 0205-perf-change-smmu-print-level-optimize-ccache-flush.patch
Patch10206: 0206-fix-open-card-sleep-0.5ms-then-set-volume.patch
Patch10207: 0207-Revert-perf-change-smmu-print-level-optimize-ccache-.patch
Patch10208: 0208-perf-change-smmu-print-level.patch
Patch10209: 0209-fix-Add-dsp-op-buffer-cnt.patch
Patch10210: 0210-fix-DSP-driver-add-license-claim.patch
Patch10211: 0211-style-Code-format-compliance-modifications.patch
Patch10212: 0212-config-enable-tun-tap.patch
Patch10213: 0213-config-enable-landlock.patch
Patch10214: 0214-perf-vendor-events-riscv-Add-SiFive-P550-events.patch
Patch10215: 0215-npu-add-es5340-support.patch
Patch10216: 0216-dts-eswin-add-megrez-device-tree.patch
Patch10217: 0217-dts-megrez-add-1.6GHz.patch
Patch10218: 0218-fix-dts-megrez-audio-remove-unused-es8388.patch
Patch10219: 0219-dts-megrez-add-pwm-fan.patch
Patch10220: 0220-backport-riscv-optimize-ELF-relocation-function-in-r.patch
Patch10221: 0221-configs-enable-thermal.patch
Patch10222: 0222-fix-8250_dw-typo.patch
Patch10223: 0223-Revert-sync-drm-support-debugfs-control-virtual.patch
Patch10224: 0224-enable-CONFIG_CRYPTO_DEV_ESWIN_EIC770x-y.patch
Patch10225: 0225-sync-sync-thermal-config-for-win2030.patch
Patch10226: 0226-Use-.NOTINTERMEDIATE-or-.SECONDARY-based-on-make-ver.patch
Patch10227: 0227-gpu-img-Replace-deprecated-functions.patch
Patch10228: 0228-drivers-gpu-img-Resolve-compilation-warnings.patch
Patch10229: 0229-WIN2030-16633-feat-updata-gpu-kernel-driver-to-ddk24.patch
Patch10230: 0230-drivers-kvm-vcpu-Disabled-writing-HENVCFG-reg.patch
Patch10231: 0231-HACK-reject-sscofpmf-for-kvm.patch
Patch10232: 0232-drivers-eswin-fix-out-of-tree-compilation.patch
Patch10233: 0233-riscv-dts-eswin-add-Pine64-StarPro64.patch
Patch10234: 0234-config-add-intel-wifi-rtl.patch
Patch10235: 0235-wireless-add-BCMHD-ap12275.patch
Patch10236: 0236-configs-enable-CONFIG_BCMDHD_SDIO_IRQ.patch
Patch10237: 0237-fix-add-irq-reset-gpio-for-aw3155.patch
Patch10238: 0238-feat-sdhci-driver-add-dump_vendor_regs-function.patch
Patch10239: 0239-fix-fix-the-issue-of-emmc-cmd-timeout.patch
Patch10240: 0240-fix-remove-csr-clk-from-eth-driver.patch
Patch10241: 0241-feat-add-audio-proc-mutex.patch
Patch10242: 0242-feat-skip-the-user-memory-cache-flush.patch
Patch10243: 0243-feat-modify-the-audio-proc-license-statement.patch
Patch10244: 0244-WIN2030-14758-feat-Add-eic7702-evb-a1.dts.patch
Patch10245: 0245-WIN2030-16098-ci-dw200-support-d2d.patch
Patch10246: 0246-WIN2030-16132-feat-run-on-the-specify-die.patch
Patch10247: 0247-WIN2030-16132-feat-enc-new-feature-of-d2d-for-enc-dr.patch
Patch10248: 0248-WIN2030-16070-feat-add-eic7x-pinctrl-driver.patch
Patch10249: 0249-WIN2030-13899-fix-adapt-sdhci-driver-to-eic7702.patch
Patch10250: 0250-WIN2030-16035-refactor-support-eic7702-evb.patch
Patch10251: 0251-WIN2030-16122-feat-e31-support-dual-die-Changelogs.patch
Patch10252: 0252-WIN2030-15907-feat-audio-adaptation-for-dual-die.patch
Patch10253: 0253-WIN2030-16289-feat-support-npu-dual-die.patch
Patch10254: 0254-WIN2030-16284-fix-adapt-pinctrl-driver-for-eic7x.patch
Patch10255: 0255-WIN2030-16098-ci-dc8k-drm-driver-adapt-d2d.patch
Patch10256: 0256-WIN2030-16286-feat-2d-support-d2d-feature.patch
Patch10257: 0257-WIN2030-16035-feat-eth-Adaption-for-ethernet-d2d.patch
Patch10258: 0258-WIN2030-16035-feat-vdec-support-d2d.patch
Patch10259: 0259-WIN2030-14758-fix-dma_numa_cma_reserve-failed.patch
Patch10260: 0260-WIN2030-16035-fix-enc-dec-fix-dma-heap-error-for-d2d.patch
Patch10261: 0261-WIN2030-16098-fix-Drm-driver-add-component-failed-is.patch
Patch10262: 0262-WIN2030-16287-feat-support-es5340-for-npu-modify-ina.patch
Patch10263: 0263-WIN2030-16286-feat-fix-2d-cannot-alloc-die0-cma-addr.patch
Patch10264: 0264-WIN2030-16287-feat-suppor-tmp102-to-get-board-temper.patch
Patch10265: 0265-WIN2030-16035-feat-Add-undefined-device-information.patch
Patch10266: 0266-WIN2030-16035-feat-uninstall-the-vdec-driver-for-d2d.patch
Patch10267: 0267-WIN2030-16287-feat-support-touchscreen-gt911.patch
Patch10268: 0268-WIN2030-16233-feat-hdmi-hdcp-driver-adapt-d2d.patch
Patch10269: 0269-WIN2030-16233-fix-resolve-hdcp-compilation-issue.patch
Patch10270: 0270-WIN2030-14758-fix-venc-driver-iova-allocation-for-ve.patch
Patch10271: 0271-WIN2030-14758-fix-vdec-driver-iova-allocation-for-vd.patch
Patch10272: 0272-WIN2030-16035-refactor-implement-d2d-interrupts-moni.patch
Patch10273: 0273-WIN2030-16139-fix-optimize-hae-blit-with-stall-on-CP.patch
Patch10274: 0274-WIN2030-16271-feat-add-delay_work-for-d2d-s-adaptati.patch
Patch10275: 0275-WIN2030-16572-feat-dsp-move-dual-die-support-to-linu.patch
Patch10276: 0276-WIN2030-16576-feat-npu-drv-support-dual-die-move-to-.patch
Patch10277: 0277-WIN2030-16445-fix-Resolve-DSP-NPU-driver-compilation.patch
Patch10278: 0278-WIN2030-16035-refactor-Add-numa-node-id-of-Die0-s-cp.patch
Patch10279: 0279-WIN2030-16035-refactor-Support-ECC-mode.patch
Patch10280: 0280-WIN2030-16035-fix-Fixbug-double-ddr-controllers-driv.patch
Patch10281: 0281-WIN2030-15078-fix-add-irq-reset-gpio-for-aw3155-in-7.patch
Patch10282: 0282-WIN2030-15365-fix-porting-modify-for-dual-e31-Change.patch
Patch10283: 0283-WIN2030-16657-fix-jenc-enc-32k-jpeg-hang.patch
Patch10284: 0284-WIN2030-16445-fix-resolve-the-issue-of-DMA-interrupt.patch
Patch10285: 0285-WIN2030-15186-fix-Fan-at-maximum-speed.patch
Patch10286: 0286-WIN2030-15186-fix-fix-slow-command-id-error.patch
Patch10287: 0287-WIN2030-16035-refactor-remove-ecc-range-from-7702-ev.patch
Patch10288: 0288-WIN2030-16286-fix-add-the-idle-timer-delay-from-500m.patch
Patch10289: 0289-WIN2030-16671-fix-drm-add-VIRTUAL-on-7702-board-Chan.patch
Patch10290: 0290-WIN2030-16286-fix-modify-license-information.patch
Patch10291: 0291-WIN2030-14758-refactor-refact-split-dmabuf.patch
Patch10292: 0292-WIN2030-16664-fix-modify-machine-model-of-7702.patch
Patch10293: 0293-WIN2030-15186-fix-change-voltage-of-7702-npu-to-1.08.patch
Patch10294: 0294-WIN2030-16664-refactor-add-evb-a3-dts-and-platform-m.patch
Patch10295: 0295-WIN2030-14758-fix-split-dmabuf.patch
Patch10296: 0296-WIN2030-16678-fix-add-hsp-clock-for-usb.patch
Patch10297: 0297-Revert-WIN2030-16678-fix-add-hsp-clock-for-usb.patch
Patch10298: 0298-WIN2030-16678-fix-add-hsp-clock-for-usb.patch
Patch10299: 0299-WIN2030-16668-feat-dump-multi-dsp-input-output.patch
Patch10300: 0300-dts-sync-eic7x-device-tree.patch
Patch10301: 0301-configs-builtin-ESWIN_IOMMU_RSV.patch
Patch10302: 0302-configs-remove-LOCALVERSION-for-eic7702.patch
Patch10303: 0303-debian-linux-image-provide-wireguard-modules.patch
Patch10304: 0304-package-add-linux-tools.patch
Patch10305: 0305-img-AXM-8-258-not-support-DRIVER_MODESET.patch
Patch10306: 0306-dts-enable-7702-d1_gpu.patch
Patch10307: 0307-eic7700-megrez-add-opp-table-for-1.5G-1.8G.patch
Patch10308: 0308-clk-eswin-add-force-1.8ghz-option.patch
Patch10309: 0309-dts-eic770x-megrez-add-force-1.8Ghz.patch
Patch10310: 0310-megrez-add-disable-wp-broken-cd-in-sdio.patch
Patch10311: 0311-eth-eswin-stmmac-disable-iommu.patch
Patch10312: 0312-configs-eic7702-add-initrd-support.patch
Patch10313: 0313-config-eic770x-cpufreq-governor-performance-as-defau.patch
Patch10314: 0314-megrez-support-rtc-m41t11.patch
Patch10315: 0315-milkv-megrez-fix-sd-card-delay_code.patch
Patch10316: 0316-riscv-dts-eswin-Add-1.8G-support-for-StarPro64.patch
Patch10317: 0317-WIN2030-15704-feat-Add-devfreq-support.patch
Patch10318: 0318-WIN2030-15754-feat-VI-dw200-add-devfreq-support.patch
Patch10319: 0319-WIN2030-16526-feat-g2d-add-devfreq-support.patch
Patch10320: 0320-WIN2030-16515-feat-venc-venc-add-devfreq-support.patch
Patch10321: 0321-WIN2030-16532-feat-vdec-add-devfreq-support.patch
Patch10322: 0322-WIN2030-15704-feat-Centralize-the-OOP-table.patch
Patch10323: 0323-WIN2030-15704-fix-npu-power-off-when-npu-sleep.patch
Patch10324: 0324-WIN2030-16551-feat-npu-drv-support-device-frequency.patch
Patch10325: 0325-WIN2030-16578-fix-npu-opp-dts-node-modify.patch
Patch10326: 0326-WIN2030-16230-feat-audio-add-sof-func.patch
Patch10327: 0327-WIN2030-16445-fix-adjust-HDMI-phy-voltage.patch
Patch10328: 0328-WIN2030-15365-fix-remove-error-message-when-try-lock.patch
Patch10329: 0329-WIN2030-14758-feat-Add-API-for-remapping-malloc-buff.patch
Patch10330: 0330-WIN2030-16445-fix-audio-driver-add-24-bits-support.patch
Patch10331: 0331-WIN2030-16740-feat-support-z530-board.patch
Patch10332: 0332-WIN2030-16760-feat-adapt-eth-driver-to-board-z530.patch
Patch10333: 0333-WIN2030-16445-fix-fix-the-issue-of-audio-recording.patch
Patch10334: 0334-WIN2030-16445-fix-NPU-driver-add-switch-for-perf-fun.patch
Patch10335: 0335-WIN2030-16445-fix-DSP-driver-add-switch-for-perf-fun.patch
Patch10336: 0336-WIN2030-16760-feat-modify-sdio-s-delay-to-adapt-to-z.patch
Patch10337: 0337-WIN2030-16445-fix-fix-the-issue-of-no-pcm-node-on-di.patch
Patch10338: 0338-WIN2030-14758-feat-add-interleave-dts.patch
Patch10339: 0339-WIN2030-16412-feat-DMA-memcopy-kernel-driver.patch
Patch10340: 0340-WIN2030-16810-fix-npu-devfeq-bug-fix.patch
Patch10341: 0341-WIN2030-16733-feat-audio-perf-for-rtc-processing.patch
Patch10342: 0342-WIN2030-16812-feat-hdmi-support-2880x1800-90-output.patch
Patch10343: 0343-WIN2030-16813-chore-disable-IPA-adjust-with-target.patch
Patch10344: 0344-WIN2030-16816-fix-fix-the-DSP-issue-of-perf-function.patch
Patch10345: 0345-WIN2030-16831-fix-Delete-HDMI-Audio-error-printing.patch
Patch10346: 0346-WIN2030-16760-feat-adapt-eth-dly-params-to-7702-inte.patch
Patch10347: 0347-WIN2030-14758-feat-Select-cipher-as-default.patch
Patch10348: 0348-WIN2030-16550-fix-7702-interleave-can-not-display-is.patch
Patch10349: 0349-WIN2030-16412-feat-change-mode-0660.patch
Patch10350: 0350-WIN2030-16848-fix-buffer-overflow-by-print-info.patch
Patch10351: 0351-WIN2030-16797-fix-Resolve-the-issue-of-abnormal-stac.patch
Patch10352: 0352-WIN2030-16860-feat-fix-96k-palyback-error.patch
Patch10353: 0353-WIN2030-16832-feat-fix-bug-for-z530-reboot-Strange-n.patch
Patch10354: 0354-WIN2030-16857-fix-dsp-pm-devfreq-bug-fix.patch
Patch10355: 0355-WIN2030-14758-feat-clk-support-set-default-cpu-freq.patch
Patch10356: 0356-WIN2030-16883-fix-npu-die1-clock-miss.patch
Patch10357: 0357-WIN2030-16692-fix-improve-numa-node-id-of-each-modul.patch
Patch10358: 0358-WIN2030-16746-feat-support-7700d314-and-7700s314.patch
Patch10359: 0359-dts-eswin-rename-d0_cpu_opp_table-to-cpu_opp_table.patch
Patch10360: 0360-npu-sync-1230-eswin-code.patch
Patch10361: 0361-vvcam_dwe_driver-sync-eswin-20241230-code.patch
Patch10362: 0362-dts-sync-eswin-gmac0-1-config.patch
Patch10363: 0363-configs-eswin-add-DEVFREQ_GOV_-PERFORMANCE-POWERSAVE.patch
Patch10364: 0364-dts-eswin-adjust-memory-node-order.patch
Patch10365: 0365-WIN2030-14758-feat-L3-cache-flush-all.patch
Patch10366: 0366-WIN2030-14758-fix-cipher-Add-tbus-property-for-ciphe.patch
Patch10367: 0367-WIN2030-16898-feat-revert-reboot-generate-noise-bug.patch
Patch10368: 0368-WIN2030-16701-fix-die1-uart-not-inited-use-uart0-bot.patch
Patch10369: 0369-WIN2030-16708-fix-Fix-squeezenet-bug.patch
Patch10370: 0370-WIN2030-16550-feat-Differentiate-output-devices-for-.patch
Patch10371: 0371-WIN2030-16550-fix-Dewarp-pm-devfreq-bug-fix.patch
Patch10372: 0372-WIN2030-16607-feat-adapt-new-eth-params-to-7702-evb.patch
Patch10373: 0373-WIN2030-16949-fix-resolve-HDMI-driver-memory-leak-is.patch
Patch10374: 0374-WIN2030-15186-feat-support-tps549d22-amd-tmp102-in-7.patch
Patch10375: 0375-WIN2030-16550-perf-Optimize-dma-performance.patch
Patch10376: 0376-WIN2030-16501-fix-Add-vi-config-TBU.patch
Patch10377: 0377-WIN2030-16686-feat-add-dma-channel-device-filter.patch
Patch10378: 0378-WIN2030-16910-feat-add-numa-support-for-770x.patch
Patch10379: 0379-WIN2030-16969-fix-i2s-binding-DMA-channels.patch
Patch10380: 0380-WIN2030-16919-feat-Apply-numa-early-node-patch-from-.patch
Patch10381: 0381-WIN2030-16919-fix-d2d-cpu-volatge-opp-table-support.patch
Patch10382: 0382-WIN2030-16919-fix-select-HAVE_SETUP_PER_CPU_AREA-if-.patch
Patch10383: 0383-WIN2030-16962-feat-enable-dual-4K-display-for-Xorg.patch
Patch10384: 0384-WIN2030-16686-feat-support-memcp-for-7702.patch
Patch10385: 0385-WIN2030-17015-fix-fix-the-issue-of-44.1k-audio-playb.patch
Patch10386: 0386-WIN2030-16900-feature-support-sbc-display.patch
Patch10387: 0387-WIN2030-16891-fix-llc-drv-add-set-npu-default-voltag.patch
Patch10388: 0388-WIN2030-16900-fix-Close-the-dsi-config-in-default-.d.patch
Patch10389: 0389-WIN2030-16813-fix-adjust-critical-temperature.patch
Patch10390: 0390-WIN2030-16813-fix-corrected-critical-temperature.patch
Patch10391: 0391-WIN2030-14758-feat-Dump-tbu-attached-device-list.patch
Patch10392: 0392-WIN2030-17068-fix-dsp-drv-mem-leak.patch
Patch10393: 0393-WIN2030-17055-feat-npu-set-voltage-modify.patch
Patch10394: 0394-WIN2030-16872-feat-hdmi-driver-adapt-2.2-2.8k-BOE-sc.patch
Patch10395: 0395-WIN2030-14758-perf-Improve-GPU-mmu-operation-and-sch.patch
Patch10396: 0396-WIN2030-17070-fix-dsp-drv-module-refcnt-problem.patch
Patch10397: 0397-WIN2030-16980-fix-Dvb-drm-virtual-debugfs-node-reg.patch
Patch10398: 0398-WIN2030-14758-fix-Bug-introduced-by-Improve-GPU-mmu.patch
Patch10399: 0399-WIN2030-16409-fix-fixed-dsp-dmabuf-issue-Changelogs-.patch
Patch10400: 0400-WIN2030-17055-feat-npu-set-voltage-modify.patch
Patch10401: 0401-WIN2030-16412-feat-Optimize-dma-channel-request.patch
Patch10402: 0402-fix-power-down-all-tbus-at-start-up.patch
Patch10403: 0403-fix-sifive-ccache_flush64_range.patch
Patch10404: 0404-iommu-eswin-sync-remove-internal-arguments-from-of_p.patch
Patch10405: 0405-config-sync-from-eic7700_defconfig.patch
Patch10406: 0406-iommu-eswin-lower-the-priority-of-TBU-dump.patch
Patch10407: 0407-star64pro-megrez-fix-npu-supply-for-npu-init.patch
Patch10408: 0408-fix-Dvb-and-z530-boot-failed-issue.patch
Patch10409: 0409-feature-Add-eic770x-OTP-driver.patch
Patch10410: 0410-feat-reset-driver-fit-for-upstream.patch
Patch10411: 0411-feat-add-npu-usage-Changelogs.patch
Patch10412: 0412-fix-2d-kernel-stack-warning-after-reboot.patch
Patch10413: 0413-feat-clk-driver-fit-for-upstream.patch
Patch10414: 0414-feat-modify-npu-dts-voltage.patch
Patch10415: 0415-fix-Solve-no-power-of-tp549d22-when-cold-boot.patch
Patch10416: 0416-fix-dambuf-helper-get-the-mutex-while-operating-on-t.patch
Patch10417: 0417-fix-D314-sdio-delay_code.patch
Patch10418: 0418-fix-dambuf-helper-fix-bug-of-heap-object-release.patch
Patch10419: 0419-fix-do-not-print-message-when-failed-mem.patch
Patch10420: 0420-fix-eswin-ai-dsp-fix-gcc-14-build-error.patch
Patch10421: 0421-config-fs-enable-xfs-gfs-f2fs-zonefs-for-eic7700x.patch
Patch10422: 0422-config-drm-nouveau-as-module-for-eic7700x.patch
Patch10423: 0423-config-memory-enable-zswap.patch
Patch10424: 0424-config-scsi-enable-scsi-config-for-eic7700x.patch
Patch10425: 0425-config-net-enable-net-device-for-eic7700x.patch
Patch10426: 0426-config-net-enable-net-options-for-eic7700x.patch
Patch10427: 0427-config-net-disable-realtek-phy-for-eic7700x.patch
Patch10428: 0428-dts-eswin-gmac-use-rgmii-txid-as-phy-mode.patch
Patch10429: 0429-configs-eswin-enable-REALTEK_PHY-as-builtin.patch
Patch10430: 0430-dts-eswin-p550-add-disable-wp-broken-cd.patch
Patch10431: 0431-Revert-riscv-dts-eswin-Add-1.8G-support-for-StarPro6.patch
Patch10432: 0432-Add-modules-required-to-run-strongswan-as-per.patch
Patch10433: 0433-Enable-L2TP.patch
Patch10434: 0434-drm-eswin-es_dw_hdmi-allow-non-standard-pixclk.patch
Patch10435: 0435-drm-eswin-clean-hwcursor-state-when-enabling-the-dis.patch
Patch10436: 0436-drm-eswin-reject-framebuffers-with-misaligned-pitch.patch
Patch10437: 0437-feat-merge-feature-vpu7702-branch.patch
Patch10438: 0438-fix-2d-2d-isr-interrupt-call-muetx-err.patch
Patch10439: 0439-feat-support-osm-dts.patch
Patch10440: 0440-fix-modify-mpq8785-critical-uint-and-es5340-lable.patch
Patch10441: 0441-feat-support-capture-for-osm-codec.patch
Patch10442: 0442-feat-npu-proc-add-voltage-and-frequency.patch
Patch10443: 0443-fix-disable-cca-pvt0-and-timer1.patch
Patch10444: 0444-fix-disable-regulator-always-on-feature.patch
Patch10445: 0445-fix-pwm-support-inverted.patch
Patch10446: 0446-fix-board-eic770x-adaptive-memory-size.patch
Patch10447: 0447-feat-kernel-Add-CacheFlushAll-API-for-lib_memory.patch
Patch10448: 0448-fix-Fix-cnoc-npu-timeout-problem.patch
Patch10449: 0449-fix-use-rgmii-txid-as-phy-mode-for-gmac.patch
Patch10450: 0450-feat-sbc-support-rtc-pcf85063a.patch
Patch10451: 0451-fix-vc-opt-error-log-for-redup-interrupts.patch
Patch10452: 0452-feature-add-7702vpu-dts.patch
Patch10453: 0453-fix-2d-hae-disable-powersaving-for-version-0330.patch
Patch10454: 0454-fix-modify-evb-AX-dvb-d314-eth-para-to-fit-0.9V.patch
Patch10455: 0455-fix-npu-dsp-cpu-gpu-support-IPA.patch
Patch10456: 0456-chore-Reduce-the-printing-in-TBU.patch
Patch10457: 0457-fix-fix-mpq8785-enable-error-and-read-voltage-error.patch
Patch10458: 0458-fix-venc-opt-venc-log-while-pm-resume-suspend.patch
Patch10459: 0459-feat-support-22.01-11.025kHz.patch
Patch10460: 0460-feat-adapt-dual-die-model.patch
Patch10461: 0461-feat-add-e31-event-op-Changelogs.patch
Patch10462: 0462-fix-resolve-the-dc-cursor-layer-issue.patch
Patch10463: 0463-Revert-feature-add-7702vpu-dts.patch
Patch10464: 0464-fix-fix-dma-buffersize.patch
Patch10465: 0465-fix-enable-cpu-gov-userspace.patch
Patch10466: 0466-fix-Resolve-the-issue-of-system-crashes.patch
Patch10467: 0467-fix-fix-dma-period-size-and-cnt-to-fit-24-16-32bit.patch
Patch10468: 0468-feat-turne-on-NPU-perf.patch
Patch10469: 0469-fix-revert-dma-fix.patch
Patch10470: 0470-fix-revert-dma.patch
Patch10471: 0471-fix-dsp-pm-notifier-problem.patch
Patch10472: 0472-fix-disable-cpu-1.4G-upper-of-evb.patch
Patch10473: 0473-riscv-module-Optimize-PLT-GOT-entry-counting.patch
Patch10474: 0474-riscv-module-fix-compilation-error-of-kvrealloc.patch
Patch10475: 0475-arch-add-ARCH_HAS_KERNEL_FPU_SUPPORT.patch
Patch10476: 0476-fix-fix-pacmsg-bug.patch
Patch10477: 0477-feat-make-dma-period-size-under-500ms.patch
Patch10478: 0478-fix-modify-i2c_ctrlX-mem-region-size-form-64K-to-32K.patch
Patch10479: 0479-fix-Modify-tps549d22-enable-sequence-of-software-cfg.patch
Patch10480: 0480-feat-support-eic7702-d560.patch
Patch10481: 0481-feat-add-DMA-malloc-to-dmabuf-driver.patch
Patch10482: 0482-feat-dma-memcp-add-sync-and-async-notifier.patch
Patch10483: 0483-feat-add-memcp-offset-overflow-check.patch
Patch10484: 0484-fix-add-disable-wp-in-sdio.patch
Patch10485: 0485-fix-enable-usb2.0-hub.patch
Patch10486: 0486-feat-adapt-to-vpu7702-smmu-cfg-drv.patch
Patch10487: 0487-feat-update-dts-for-eic7702_vpu.patch
Patch10488: 0488-feat-Merge-branch-feature-vi-into-win2030-dev.patch
Patch10489: 0489-fix-Resolve-the-issue-of-NPU-reset.patch
Patch10490: 0490-fix-fix-multi-process-npu-ioctl-bug.patch
Patch10491: 0491-feat-vpu7702-smmu-cfg-modify.patch
Patch10492: 0492-feat-eth-ETH-tuning-in-EIC7702_D560.patch
Patch10493: 0493-fix-clear-ecc-interrupt-anytime.patch
Patch10494: 0494-fix-pcie-check-clk-before-init.patch
Patch10495: 0495-feat-adapt-ap6256.patch
Patch10496: 0496-feat-to-support-both-evb-and-televpu.patch
Patch10497: 0497-fix-fix-evb-vi-catpure-image.patch
Patch10498: 0498-fix-pcie-tbu-error.patch
Patch10499: 0499-feat-Export-die-idx-pin.patch
Patch10500: 0500-feat-add-es-fand-function.patch
Patch10501: 0501-fix-dvp2axi-kernel-warning.patch
Patch10502: 0502-fix-modify-the-reading-method-of-rpm.patch
Patch10503: 0503-feature-Add-kernel-eic7702-d560-interleave-dts.patch
Patch10504: 0504-fix-NPU-enable-1.5G-performance.patch
Patch10505: 0505-fix-VPU-model-reading-erro.patch
Patch10506: 0506-feat-update-memory-for-mmz-and-bar2.patch
Patch10507: 0507-feat-support-SOC-CPU-up-voltage.patch
Patch10508: 0508-fix-fix-dc-endpoint-index.patch
Patch10509: 0509-feat-osm-dts-add-gpio-pinctrl-script.patch
Patch10510: 0510-fix-Revert-some-err-dts-changes-for-VI-Merge.patch
Patch10511: 0511-feat-update-escl-linux-dependency.patch
Patch10512: 0512-feat-sbc-support-i2c-spi.patch
Patch10513: 0513-feature-Sync-d560-dts-config.patch
Patch10514: 0514-fix-vpu7702-streamid-problem.patch
Patch10515: 0515-feat-sbc-vi.patch
Patch10516: 0516-fix-delete-warning-log.patch
Patch10517: 0517-style-fix-the-warning-in-DTS.patch
Patch10518: 0518-fix-sata-downspeed-issue-on-die1-debug.patch
Patch10519: 0519-feat-Add-SD-card-detect.patch
Patch10520: 0520-style-fix-the-warning-in-DTS.patch
Patch10521: 0521-feat-support-dewarp-in-7702.patch
Patch10522: 0522-fix-fix-sbc-camera-dts-warning-log.patch
Patch10523: 0523-feat-d314-vi-support.patch
Patch10524: 0524-fix-fix-system-hang-after-run-isp-and-sample_vps-2.patch
Patch10525: 0525-feat-remove-v4l2_pm-in-video-open-close.patch
Patch10526: 0526-fix-KASAN-global-out-of-bounds.patch
Patch10527: 0527-fix-Fix-d560-interleave-cpufreq-dt-probe-fail-issue.patch
Patch10528: 0528-fix-solve-guvcview-print-err-log.patch
Patch10529: 0529-fix-resolve-the-issue-of-slow-fan-speed.patch
Patch10530: 0530-fix-fix-isp-isp_media_server-error-in-debian.patch
Patch10531: 0531-feat-d314-isp-support.patch
Patch10532: 0532-feat-enable-ddr-ecc-for-televpu.patch
Patch10533: 0533-config-win2030-enable-CONFIG_TASK_IO_ACCOUNTING.patch
Patch10534: 0534-config-win2030-enable-CONFIG_FUSE_FS.patch
Patch10535: 0535-dts-add-milkv-megrez-nx.dts.patch
Patch10536: 0536-riscv-dts-eswin-some-starpro64-dt-changes.patch
Patch10537: 0537-mmc-sdhci-of-eswin-ignore-bogus-small-delay-windows.patch
Patch10538: 0538-riscv-configs-enable-Motorcomm-PHY-driver.patch
Patch10539: 0539-riscv-dts-eswin-starpro64-tweak-GMAC0-RX-delay.patch
Patch10540: 0540-PCI-eswin-keep-PCIe-alive-at-shutdown.patch
Patch10541: 0541-riscv-dts-megrez-nx-fix-sata-act-led-gpio.patch
Patch10542: 0542-ci-add-build.patch
Patch10543: 0543-fix-fix-ubuntu-up-warning-and-terminal-lag.patch
Patch10544: 0544-fix-disable-sdio1-by-default-for-eic7700-sbc-a1-boar.patch
Patch10545: 0545-feat-add-new-perf-interface.patch
Patch10546: 0546-feat-update-dts-for-eic7702_pcie.patch
Patch10547: 0547-feat-Reserve-memory-for-version-info.patch
Patch10548: 0548-fix-fix-SBC-MIPI-spupport-MP-test.patch
Patch10549: 0549-feat-Reserve-memory-for-board-info.patch
Patch10550: 0550-feature-Enable-pstore-feature.patch
Patch10551: 0551-fix-Fix-invalid-GPIO-for-D560-gmac.patch
Patch10552: 0552-feat-add-vpu7702_pcie_factory.dts.patch
Patch10553: 0553-feat-use-dev_dbg-to-print-the-uart-noc-err-log.patch
Patch10554: 0554-fix-adapt-d560-audio-input.patch
Patch10555: 0555-feat-Reserve-memory-for-bd-info.patch
Patch10556: 0556-feat-to-support-vpu7702-pcie-A2-card.patch
Patch10557: 0557-fix-fix-modify-SBC-MIPI-path.patch
Patch10558: 0558-feat-vpu-set-npu-freq-to-1G.patch
Patch10559: 0559-feat-Enable-lpcpu-fw-load-for-vpu7702.patch
Patch10560: 0560-fix-Open-2d-node.patch
Patch10561: 0561-fix-using-algorithms-to-filter.patch
Patch10562: 0562-feat-npu-driver-print-valt-and-rate.patch
Patch10563: 0563-fix-fix-lpcpu-dump-failed-Changelogs-1.-fix-lpcpu-du.patch
Patch10564: 0564-fix-modify-model-name.patch
Patch10565: 0565-fix-modify-the-reference-temperature.patch
Patch10566: 0566-feat-support-eic7700-fccsp-evb-a1.patch
Patch10567: 0567-chore-Make-es_proc-as-common-interfaces.patch
Patch10568: 0568-fix-lspci-issue-after-reboot.patch
Patch10569: 0569-feat-revert-lpcpu-modifications.patch
Patch10570: 0570-feat-Display-LOGO-during-kernel-bootup.patch
Patch10571: 0571-chore-fix-es_porc-builtin-issue.patch
Patch10572: 0572-feat-2d-add-hardware-load-statistics-with-proc-show.patch
Patch10573: 0573-fix-fix-EVB-MIPI-spupport-MP-test.patch
Patch10574: 0574-fix-usb-dwc3-eswin-Fix-section-mismatch.patch
Patch10575: 0575-fix-drivers-sound-eswin-Add-mutex-in-module_exit.patch
Patch10576: 0576-fix-smmu-lockdep_assert_held-error-in-groups.patch
Patch10577: 0577-feature-Fix-kexec-job-depend-on-proc-iomem-reserved.patch
Patch10578: 0578-feature-Add-CONFIG_KEXEC-and-SYSRQ-config.patch
Patch10579: 0579-feat-Add-statistics-of-NPU-frame-rate.patch
Patch10580: 0580-fix-modify-temperature-to-65-75-105.patch
Patch10581: 0581-fix-pvt0-label-info-inaccurate.patch
Patch10582: 0582-feature-Remove-CONFIG_DEBUG_INFO.patch
Patch10583: 0583-feat-Merge-branch-feature-vi-into-dev.patch
Patch10584: 0584-fix-remove-DRIVER_MODSET-flag-from-img.patch
Patch10585: 0585-fix-enable-npu-and-dsp-in-dts-Changelogs.patch
Patch10586: 0586-fix-dmabuf-dma_resv-lock-was-not-held.patch
Patch10587: 0587-fix-fix-vi-0630.patch
Patch10588: 0588-feature-Add-kdb-config-and-ftrace-config.patch
Patch10589: 0589-perf-Optimize-CPU-voltage-and-cpufreq-control.patch
Patch10590: 0590-feat-add-aicard-feature-Changelogs.patch
Patch10591: 0591-fix-vpu-pcie-streamid-problem.patch
Patch10592: 0592-fix-eic7700-cpu-voltage-and-cpufreq-control-failed.patch
Patch10593: 0593-feat-Update-vpu7702-pcie-a2.dts.patch
Patch10594: 0594-fix-2d-hardware-usage-timer-func-release-mutex-faile.patch
Patch10595: 0595-fix-fix-nid-check-bug-in-flush_all.patch
Patch10596: 0596-chore-move-es_proc.h-to-commom-dir.patch
Patch10597: 0597-fix-check-d2d-recovery-status.patch
Patch10598: 0598-fix-fix-smmu-print-level.patch
Patch10599: 0599-fix-disable-wifi-by-default.patch
Patch10600: 0600-feature-Support-trigger-kdump-when-rcu-stall.patch
Patch10601: 0601-fix-clear-log-for-ap6256.patch
Patch10602: 0602-fix-vdec-fix-dead-lock-issue-for-vdec-driver.patch
Patch10603: 0603-fix-Add-multi-batch-frame-rate-statistics.patch
Patch10604: 0604-feat-Enable-npu-power-node.patch
Patch10605: 0605-fix-fix-no-dewarp-devnode-on-7702.patch
Patch10606: 0606-fix-cpufreq-switch-failed.patch
Patch10607: 0607-feat-Support-ESWIN-s-TRNG.patch
Patch10608: 0608-feat-support-fccsp-evb-mipi-csi.patch
Patch10609: 0609-fix-fix-some-vi-warning-in-0630.patch
Patch10610: 0610-feat-support-IPA-in-VPU.patch
Patch10611: 0611-feat-support-eswin-s-hwrng.patch
Patch10612: 0612-feat-support-fccsp-evb-mipi-csi.patch
Patch10613: 0613-fix-clear-log-for-wifi-stop.patch
Patch10614: 0614-feature-Add-reset-trigger-kdump-driver.patch
Patch10615: 0615-feature-Sync-config-from-eic7700_defconfig.patch
Patch10616: 0616-feature-Enable-pstore-feature-on-all-eic7700-eic7702.patch
Patch10617: 0617-fix-fix-MIPI-DSI-reboot-panic.patch
Patch10618: 0618-fix-add-dmabuf_helper-params-check.patch
Patch10619: 0619-fix-Dual-die-rng-register.patch
Patch10620: 0620-perf-dsiable-d2d-driver.patch
Patch10621: 0621-feat-Refactor-PACMSG.patch
Patch10622: 0622-fix-venc-venc-run-in-D1-cause-system-hang.patch
Patch10623: 0623-fix-fusb303b-mutex-lock-used-before-initialization.patch
Patch10624: 0624-fix-2d-kernel-stack-on-d2d-cherry-pick-4559ee5-from-.patch
Patch10625: 0625-fix-2d-suspend-failed-cherry-pick-0284684-from-pm.patch
Patch10626: 0626-fix-2d-power-off-delay-cherry-pick-c81694e-from-pm.patch
Patch10627: 0627-fix-2d-process-stuck-cherry-pick-164de56-from-pm.patch
Patch10628: 0628-feat-implement-cpu-read-data-from-lpcpu.patch
Patch10629: 0629-fix-enable-pvt0-in-7702-boards-by-default.patch
Patch10630: 0630-fix-d2d-support-thermal.patch
Patch10631: 0631-fix-disabled-isp-for-feature-not-ready.patch
Patch10632: 0632-fix-disabled-isp-for-feature-not-ready.patch
Patch10633: 0633-feat-new-board-u2-evb.patch
Patch10634: 0634-fix-fix-no-dewarp-dev-node.patch
Patch10635: 0635-fix-2d-close-power-mangemnet.patch
Patch10636: 0636-fix-Enable-sdio1-by-default-for-eic7700-sbc-a1-board.patch
Patch10637: 0637-dts-sync-ramoops-for-megrez-nx-star64pro.patch
Patch10638: 0638-config-sync-eic7700-config.patch
Patch10639: 0639-UPSTREAM-selftests-riscv-Generalize-mm-selftests.patch
Patch10640: 0640-UPSTREAM-docs-riscv-Define-behavior-of-mmap.patch
Patch10641: 0641-UPSTREAM-riscv-selftests-Remove-mmap-hint-address-ch.patch
Patch10642: 0642-UPSTREAM-Revert-RISC-V-mm-Document-mmap-changes.patch
Patch10643: 0643-header-workarounds.patch
Patch10644: 0644-stop-triggering-vmlinux-rebuild.patch
Patch10645: 0645-Add-missing-newline.patch
Patch10646: 0646-uninvert-the-fan.patch
Patch10647: 0647-Reduce-crit-threshold-temp-to-85000.patch
Patch10648: 0648-eswin-dsp-fixes.patch
Patch10649: 0649-remove-mmz-vb-reserved-memory-ranges.patch
Patch10650: 0650-Add-NPU-enabled-variants-of-dtbs.patch
Patch10651: 0651-Bring-back-1.8GHz-to-STARPro64.patch
Patch10652: 0652-remove-makefile-reference-for-non-existent-directory.patch





%endif

# empty final patch to facilitate testing of kernel patches
Patch999999: linux-kernel-test.patch

# END OF PATCH DEFINITIONS

%description
The kernel meta package

#
# This macro does requires, provides, conflicts, obsoletes for a kernel package.
#	%%kernel_reqprovconf [-o] <subpackage>
# It uses any kernel_<subpackage>_conflicts and kernel_<subpackage>_obsoletes
# macros defined above.
#
%define kernel_reqprovconf(o) \
%if %{-o:0}%{!-o:1}\
Provides: kernel = %{specversion}-%{pkg_release}\
%endif\
Provides: kernel-%{_target_cpu} = %{specrpmversion}-%{pkg_release}%{uname_suffix %{?1:+%{1}}}\
Provides: kernel-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel%{?1:-%{1}}-modules-core-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires(pre): %{kernel_prereq}\
Requires(pre): %{initrd_prereq}\
Requires(pre): ((linux-firmware >= 20150904-56.git6ebf5d57) if linux-firmware)\
Recommends: linux-firmware\
Requires(preun): systemd >= 200\
Conflicts: xfsprogs < 4.3.0-1\
Conflicts: xorg-x11-drv-vmmouse < 13.0.99\
%{expand:%%{?kernel%{?1:_%{1}}_conflicts:Conflicts: %%{kernel%{?1:_%{1}}_conflicts}}}\
%{expand:%%{?kernel%{?1:_%{1}}_obsoletes:Obsoletes: %%{kernel%{?1:_%{1}}_obsoletes}}}\
%{expand:%%{?kernel%{?1:_%{1}}_provides:Provides: %%{kernel%{?1:_%{1}}_provides}}}\
# We can't let RPM do the dependencies automatic because it'll then pick up\
# a correct but undesirable perl dependency from the module headers which\
# isn't required for the kernel proper to function\
AutoReq: no\
AutoProv: yes\
%{nil}


%package doc
Summary: Various documentation bits found in the kernel source
Group: Documentation
%description doc
This package contains documentation files from the kernel
source. Various bits of information about the Linux kernel and the
device drivers shipped with it are documented in these files.

You'll want to install this package if you need a reference to the
options that can be passed to Linux kernel modules at load time.


%package headers
Summary: Header files for the Linux kernel for use by glibc
Obsoletes: glibc-kernheaders < 3.0-46
Provides: glibc-kernheaders = 3.0-46
%if 0%{?gemini}
Provides: kernel-headers = %{specversion}-%{release}
Obsoletes: kernel-headers < %{specversion}
%endif
%description headers
Kernel-headers includes the C header files that specify the interface
between the Linux kernel and userspace libraries and programs.  The
header files define structures and constants that are needed for
building most standard programs and are also needed for rebuilding the
glibc package.

%package cross-headers
Summary: Header files for the Linux kernel for use by cross-glibc
%if 0%{?gemini}
Provides: kernel-cross-headers = %{specversion}-%{release}
Obsoletes: kernel-cross-headers < %{specversion}
%endif
%description cross-headers
Kernel-cross-headers includes the C header files that specify the interface
between the Linux kernel and userspace libraries and programs.  The
header files define structures and constants that are needed for
building most standard programs and are also needed for rebuilding the
cross-glibc package.

%package debuginfo-common-%{_target_cpu}
Summary: Kernel source files used by %{name}-debuginfo packages
Provides: installonlypkg(kernel)
%description debuginfo-common-%{_target_cpu}
This package is required by %{name}-debuginfo subpackages.
It provides the kernel source files common to all builds.

%if %{with_perf}
%package -n perf
%if 0%{gemini}
Epoch: %{gemini}
%endif
Summary: Performance monitoring for the Linux kernel
Requires: bzip2
%description -n perf
This package contains the perf tool, which enables performance monitoring
of the Linux kernel.

%package -n perf-debuginfo
%if 0%{gemini}
Epoch: %{gemini}
%endif
Summary: Debug information for package perf
Requires: %{name}-debuginfo-common-%{_target_cpu} = %{specrpmversion}-%{release}
AutoReqProv: no
%description -n perf-debuginfo
This package provides debug information for the perf package.

# Note that this pattern only works right to match the .build-id
# symlinks because of the trailing nonmatching alternation and
# the leading .*, because of find-debuginfo.sh's buggy handling
# of matching the pattern against the symlinks file.
%{expand:%%global _find_debuginfo_opts %{?_find_debuginfo_opts} -p '.*%%{_bindir}/perf(\.debug)?|.*%%{_libexecdir}/perf-core/.*|.*%%{_libdir}/libperf-jvmti.so(\.debug)?|XXX' -o perf-debuginfo.list}

%package -n python3-perf
%if 0%{gemini}
Epoch: %{gemini}
%endif
Summary: Python bindings for apps which will manipulate perf events
%description -n python3-perf
The python3-perf package contains a module that permits applications
written in the Python programming language to use the interface
to manipulate perf events.

%package -n python3-perf-debuginfo
%if 0%{gemini}
Epoch: %{gemini}
%endif
Summary: Debug information for package perf python bindings
Requires: %{name}-debuginfo-common-%{_target_cpu} = %{specrpmversion}-%{release}
AutoReqProv: no
%description -n python3-perf-debuginfo
This package provides debug information for the perf python bindings.

# the python_sitearch macro should already be defined from above
%{expand:%%global _find_debuginfo_opts %{?_find_debuginfo_opts} -p '.*%%{python3_sitearch}/perf.*so(\.debug)?|XXX' -o python3-perf-debuginfo.list}

# with_perf
%endif

%if %{with_tools}
%package -n %{package_name}-tools
Summary: Assortment of tools for the Linux kernel
%ifarch %{cpupowerarchs}
Provides:  cpupowerutils = 1:009-0.6.p1
Obsoletes: cpupowerutils < 1:009-0.6.p1
Provides:  cpufreq-utils = 1:009-0.6.p1
Provides:  cpufrequtils = 1:009-0.6.p1
Obsoletes: cpufreq-utils < 1:009-0.6.p1
Obsoletes: cpufrequtils < 1:009-0.6.p1
Obsoletes: cpuspeed < 1:1.5-16
Requires: %{package_name}-tools-libs = %{specrpmversion}-%{release}
%endif
%define __requires_exclude ^%{_bindir}/python
%description -n %{package_name}-tools
This package contains the tools/ directory from the kernel source
and the supporting documentation.

%package -n %{package_name}-tools-libs
Summary: Libraries for the kernels-tools
%description -n %{package_name}-tools-libs
This package contains the libraries built from the tools/ directory
from the kernel source.

%package -n %{package_name}-tools-libs-devel
Summary: Assortment of tools for the Linux kernel
Requires: %{package_name}-tools = %{version}-%{release}
%ifarch %{cpupowerarchs}
Provides:  cpupowerutils-devel = 1:009-0.6.p1
Obsoletes: cpupowerutils-devel < 1:009-0.6.p1
%endif
Requires: %{package_name}-tools-libs = %{version}-%{release}
Provides: %{package_name}-tools-devel
%description -n %{package_name}-tools-libs-devel
This package contains the development files for the tools/ directory from
the kernel source.

%package -n %{package_name}-tools-debuginfo
Summary: Debug information for package %{package_name}-tools
Requires: %{name}-debuginfo-common-%{_target_cpu} = %{version}-%{release}
AutoReqProv: no
%description -n %{package_name}-tools-debuginfo
This package provides debug information for package %{package_name}-tools.

# Note that this pattern only works right to match the .build-id
# symlinks because of the trailing nonmatching alternation and
# the leading .*, because of find-debuginfo.sh's buggy handling
# of matching the pattern against the symlinks file.
%{expand:%%global _find_debuginfo_opts %{?_find_debuginfo_opts} -p '.*%%{_bindir}/centrino-decode(\.debug)?|.*%%{_bindir}/powernow-k8-decode(\.debug)?|.*%%{_bindir}/cpupower(\.debug)?|.*%%{_libdir}/libcpupower.*|.*%%{_bindir}/turbostat(\.debug)?|.*%%{_bindir}/x86_energy_perf_policy(\.debug)?|.*%%{_bindir}/tmon(\.debug)?|.*%%{_bindir}/lsgpio(\.debug)?|.*%%{_bindir}/gpio-hammer(\.debug)?|.*%%{_bindir}/gpio-event-mon(\.debug)?|.*%%{_bindir}/gpio-watch(\.debug)?|.*%%{_bindir}/iio_event_monitor(\.debug)?|.*%%{_bindir}/iio_generic_buffer(\.debug)?|.*%%{_bindir}/lsiio(\.debug)?|.*%%{_bindir}/intel-speed-select(\.debug)?|.*%%{_bindir}/page_owner_sort(\.debug)?|.*%%{_bindir}/slabinfo(\.debug)?|.*%%{_sbindir}/intel_sdsi(\.debug)?|XXX' -o %{package_name}-tools-debuginfo.list}

%package -n rtla
%if 0%{gemini}
Epoch: %{gemini}
%endif
Summary: RTLA: Real-Time Linux Analysis tools
%description -n rtla
The rtla tool is a meta-tool that includes a set of commands that
aims to analyze the real-time properties of Linux. But, instead of
testing Linux as a black box, rtla leverages kernel tracing
capabilities to provide precise information about the properties
and root causes of unexpected results.

%package -n rv
Summary: RV: Runtime Verification
%description -n rv
Runtime Verification (RV) is a lightweight (yet rigorous) method that
complements classical exhaustive verification techniques (such as model
checking and theorem proving) with a more practical approach for
complex systems.
The rv tool is the interface for a collection of monitors that aim
analysing the logical and timing behavior of Linux.

# with_tools
%endif

%if %{with_bpftool}

%define bpftoolversion 7.3.0

%package -n bpftool
Summary: Inspection and simple manipulation of eBPF programs and maps
Version: %{bpftoolversion}
%description -n bpftool
This package contains the bpftool, which allows inspection and simple
manipulation of eBPF programs and maps.

%package -n bpftool-debuginfo
Summary: Debug information for package bpftool
Version: %{bpftoolversion}
Group: Development/Debug
Requires: %{name}-debuginfo-common-%{_target_cpu} = %{specrpmversion}-%{release}
AutoReqProv: no
%description -n bpftool-debuginfo
This package provides debug information for the bpftool package.

%{expand:%%global _find_debuginfo_opts %{?_find_debuginfo_opts} -p '.*%%{_sbindir}/bpftool(\.debug)?|XXX' -o bpftool-debuginfo.list}

# Setting "Version:" above overrides the internal {version} macro,
# need to restore it here
%define version %{specrpmversion}

# with_bpftool
%endif

%if %{with_selftests}

%package selftests-internal
Summary: Kernel samples and selftests
Requires: binutils, bpftool, iproute-tc, nmap-ncat, python3, fuse-libs
%description selftests-internal
Kernel sample programs and selftests.

# Note that this pattern only works right to match the .build-id
# symlinks because of the trailing nonmatching alternation and
# the leading .*, because of find-debuginfo.sh's buggy handling
# of matching the pattern against the symlinks file.
%{expand:%%global _find_debuginfo_opts %{?_find_debuginfo_opts} -p '.*%%{_libexecdir}/(ksamples|kselftests)/.*|XXX' -o selftests-debuginfo.list}

# with_selftests
%endif

%define kernel_gcov_package() \
%package %{?1:%{1}-}gcov\
Summary: gcov graph and source files for coverage data collection.\
%description %{?1:%{1}-}gcov\
%{?1:%{1}-}gcov includes the gcov graph and source files for gcov coverage collection.\
%{nil}

%package -n %{package_name}-abi-stablelists
Summary: The Red Hat Enterprise Linux kernel ABI symbol stablelists
AutoReqProv: no
%description -n %{package_name}-abi-stablelists
The kABI package contains information pertaining to the Red Hat Enterprise
Linux kernel ABI, including lists of kernel symbols that are needed by
external Linux kernel modules, and a yum plugin to aid enforcement.

%if %{with_kabidw_base}
%package kernel-kabidw-base-internal
Summary: The baseline dataset for kABI verification using DWARF data
Group: System Environment/Kernel
AutoReqProv: no
%description kernel-kabidw-base-internal
The package contains data describing the current ABI of the Red Hat Enterprise
Linux kernel, suitable for the kabi-dw tool.
%endif

#
# This macro creates a kernel-<subpackage>-debuginfo package.
#	%%kernel_debuginfo_package <subpackage>
#
# Explanation of the find_debuginfo_opts: We build multiple kernels (debug,
# rt, 64k etc.) so the regex filters those kernels appropriately. We also
# have to package several binaries as part of kernel-devel but getting
# unique build-ids is tricky for these userspace binaries. We don't really
# care about debugging those so we just filter those out and remove it.
%define kernel_debuginfo_package() \
%package %{?1:%{1}-}debuginfo\
Summary: Debug information for package %{name}%{?1:-%{1}}\
Requires: %{name}-debuginfo-common-%{_target_cpu} = %{specrpmversion}-%{release}\
Provides: %{name}%{?1:-%{1}}-debuginfo-%{_target_cpu} = %{specrpmversion}-%{release}\
Provides: installonlypkg(kernel)\
AutoReqProv: no\
%description %{?1:%{1}-}debuginfo\
This package provides debug information for package %{name}%{?1:-%{1}}.\
This is required to use SystemTap with %{name}%{?1:-%{1}}-%{KVERREL}.\
%{expand:%%global _find_debuginfo_opts %{?_find_debuginfo_opts} --keep-section '.BTF' -p '.*\/usr\/src\/kernels/.*|XXX' -o ignored-debuginfo.list -p '/.*/%%{KVERREL_RE}%{?1:[+]%{1}}/.*|/.*%%{KVERREL_RE}%{?1:\+%{1}}(\.debug)?' -o debuginfo%{?1}.list}\
%{nil}

#
# This macro creates a kernel-<subpackage>-devel package.
#	%%kernel_devel_package [-m] <subpackage> <pretty-name>
#
%define kernel_devel_package(m) \
%package %{?1:%{1}-}devel\
Summary: Development package for building kernel modules to match the %{?2:%{2} }kernel\
Provides: kernel%{?1:-%{1}}-devel-%{_target_cpu} = %{specrpmversion}-%{release}\
Provides: kernel-devel-%{_target_cpu} = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: kernel-devel-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Provides: installonlypkg(kernel)\
AutoReqProv: no\
Requires(pre): findutils\
Requires: findutils\
Requires: perl-interpreter\
Requires: openssl-devel\
Requires: elfutils-libelf-devel\
Requires: bison\
Requires: flex\
Requires: make\
Requires: gcc\
%if %{-m:1}%{!-m:0}\
Requires: kernel-devel-uname-r = %{KVERREL}%{uname_variant %{?1:%{1}}}\
%endif\
%description %{?1:%{1}-}devel\
This package provides kernel headers and makefiles sufficient to build modules\
against the %{?2:%{2} }kernel package.\
%{nil}

#
# This macro creates an empty kernel-<subpackage>-devel-matched package that
# requires both the core and devel packages locked on the same version.
#	%%kernel_devel_matched_package [-m] <subpackage> <pretty-name>
#
%define kernel_devel_matched_package(m) \
%package %{?1:%{1}-}devel-matched\
Summary: Meta package to install matching core and devel packages for a given %{?2:%{2} }kernel\
Requires: %{package_name}%{?1:-%{1}}-devel = %{specrpmversion}-%{release}\
Requires: %{package_name}%{?1:-%{1}}-core = %{specrpmversion}-%{release}\
%description %{?1:%{1}-}devel-matched\
This meta package is used to install matching core and devel packages for a given %{?2:%{2} }kernel.\
%{nil}

#
# kernel-<variant>-ipaclones-internal package
#
%define kernel_ipaclones_package() \
%package %{?1:%{1}-}ipaclones-internal\
Summary: *.ipa-clones files generated by -fdump-ipa-clones for kernel%{?1:-%{1}}\
Group: System Environment/Kernel\
AutoReqProv: no\
%description %{?1:%{1}-}ipaclones-internal\
This package provides *.ipa-clones files.\
%{nil}

#
# This macro creates a kernel-<subpackage>-modules-internal package.
#	%%kernel_modules_internal_package <subpackage> <pretty-name>
#
%define kernel_modules_internal_package() \
%package %{?1:%{1}-}modules-internal\
Summary: Extra kernel modules to match the %{?2:%{2} }kernel\
Group: System Environment/Kernel\
Provides: kernel%{?1:-%{1}}-modules-internal-%{_target_cpu} = %{specrpmversion}-%{release}\
Provides: kernel%{?1:-%{1}}-modules-internal-%{_target_cpu} = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: kernel%{?1:-%{1}}-modules-internal = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: installonlypkg(kernel-module)\
Provides: kernel%{?1:-%{1}}-modules-internal-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel%{?1:-%{1}}-modules-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel%{?1:-%{1}}-modules-core-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
AutoReq: no\
AutoProv: yes\
%description %{?1:%{1}-}modules-internal\
This package provides kernel modules for the %{?2:%{2} }kernel package for Red Hat internal usage.\
%{nil}

#
# This macro creates a kernel-<subpackage>-modules-extra package.
#	%%kernel_modules_extra_package [-m] <subpackage> <pretty-name>
#
%define kernel_modules_extra_package(m) \
%package %{?1:%{1}-}modules-extra\
Summary: Extra kernel modules to match the %{?2:%{2} }kernel\
Provides: kernel%{?1:-%{1}}-modules-extra-%{_target_cpu} = %{specrpmversion}-%{release}\
Provides: kernel%{?1:-%{1}}-modules-extra-%{_target_cpu} = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: kernel%{?1:-%{1}}-modules-extra = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: installonlypkg(kernel-module)\
Provides: kernel%{?1:-%{1}}-modules-extra-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel%{?1:-%{1}}-modules-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel%{?1:-%{1}}-modules-core-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
%if %{-m:1}%{!-m:0}\
Requires: kernel-modules-extra-uname-r = %{KVERREL}%{uname_variant %{?1:+%{1}}}\
%endif\
AutoReq: no\
AutoProv: yes\
%description %{?1:%{1}-}modules-extra\
This package provides less commonly used kernel modules for the %{?2:%{2} }kernel package.\
%{nil}

#
# This macro creates a kernel-<subpackage>-modules package.
#	%%kernel_modules_package [-m] <subpackage> <pretty-name>
#
%define kernel_modules_package(m) \
%package %{?1:%{1}-}modules\
Summary: kernel modules to match the %{?2:%{2}-}core kernel\
Provides: kernel%{?1:-%{1}}-modules-%{_target_cpu} = %{specrpmversion}-%{release}\
Provides: kernel-modules-%{_target_cpu} = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: kernel-modules = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: installonlypkg(kernel-module)\
Provides: kernel%{?1:-%{1}}-modules-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel%{?1:-%{1}}-modules-core-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
%if %{-m:1}%{!-m:0}\
Requires: kernel-modules-uname-r = %{KVERREL}%{uname_variant %{?1:+%{1}}}\
%endif\
AutoReq: no\
AutoProv: yes\
%description %{?1:%{1}-}modules\
This package provides commonly used kernel modules for the %{?2:%{2}-}core kernel package.\
%{nil}

#
# This macro creates a kernel-<subpackage>-modules-core package.
#	%%kernel_modules_core_package [-m] <subpackage> <pretty-name>
#
%define kernel_modules_core_package(m) \
%package %{?1:%{1}-}modules-core\
Summary: Core kernel modules to match the %{?2:%{2}-}core kernel\
Provides: kernel%{?1:-%{1}}-modules-core-%{_target_cpu} = %{specrpmversion}-%{release}\
Provides: kernel-modules-core-%{_target_cpu} = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: kernel-modules-core = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: installonlypkg(kernel-module)\
Provides: kernel%{?1:-%{1}}-modules-core-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
%if %{-m:1}%{!-m:0}\
Requires: kernel-modules-core-uname-r = %{KVERREL}%{uname_variant %{?1:+%{1}}}\
%endif\
AutoReq: no\
AutoProv: yes\
%description %{?1:%{1}-}modules-core\
This package provides essential kernel modules for the %{?2:%{2}-}core kernel package.\
%{nil}

#
# this macro creates a kernel-<subpackage> meta package.
#	%%kernel_meta_package <subpackage>
#
%define kernel_meta_package() \
%package %{1}\
summary: kernel meta-package for the %{1} kernel\
Requires: kernel-%{1}-core-uname-r = %{KVERREL}%{uname_suffix %{1}}\
Requires: kernel-%{1}-modules-uname-r = %{KVERREL}%{uname_suffix %{1}}\
Requires: kernel-%{1}-modules-core-uname-r = %{KVERREL}%{uname_suffix %{1}}\
%if "%{1}" == "rt" || "%{1}" == "rt-debug"\
Requires: realtime-setup\
%endif\
Provides: installonlypkg(kernel)\
%description %{1}\
The meta-package for the %{1} kernel\
%{nil}

%if %{with_realtime}
#
# this macro creates a kernel-rt-<subpackage>-kvm package
# %%kernel_kvm_package <subpackage>
#
%define kernel_kvm_package() \
%package %{?1:%{1}-}kvm\
Summary: KVM modules for package kernel%{?1:-%{1}}\
Group: System Environment/Kernel\
Requires: kernel%{?1:-%{1}} = %{version}-%{release}\
Provides: installonlypkg(kernel-module)\
Provides: kernel%{?1:-%{1}}-kvm-%{_target_cpu} = %{version}-%{release}\
AutoReq: no\
%description -n kernel%{?1:-%{1}}-kvm\
This package provides KVM modules for package kernel%{?1:-%{1}}.\
%{nil}
%endif

#
# This macro creates a kernel-<subpackage> and its -devel and -debuginfo too.
#	%%define variant_summary The Linux kernel compiled for <configuration>
#	%%kernel_variant_package [-n <pretty-name>] [-m] [-o] <subpackage>
#
%define kernel_variant_package(n:mo) \
%package %{?1:%{1}-}core\
Summary: %{variant_summary}\
Provides: kernel-%{?1:%{1}-}core-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Provides: installonlypkg(kernel)\
%if %{-m:1}%{!-m:0}\
Requires: kernel-core-uname-r = %{KVERREL}%{uname_variant %{?1:+%{1}}}\
Requires: kernel-%{?1:%{1}-}-modules-core-uname-r = %{KVERREL}%{uname_variant %{?1:+%{1}}}\
%endif\
%{expand:%%kernel_reqprovconf %{?1:%{1}} %{-o:%{-o}}}\
%if %{?1:1} %{!?1:0} \
%{expand:%%kernel_meta_package %{?1:%{1}}}\
%endif\
%{expand:%%kernel_devel_package %{?1:%{1}} %{!?{-n}:%{1}}%{?{-n}:%{-n*}} %{-m:%{-m}}}\
%{expand:%%kernel_devel_matched_package %{?1:%{1}} %{!?{-n}:%{1}}%{?{-n}:%{-n*}} %{-m:%{-m}}}\
%{expand:%%kernel_modules_package %{?1:%{1}} %{!?{-n}:%{1}}%{?{-n}:%{-n*}} %{-m:%{-m}}}\
%{expand:%%kernel_modules_core_package %{?1:%{1}} %{!?{-n}:%{1}}%{?{-n}:%{-n*}} %{-m:%{-m}}}\
%{expand:%%kernel_modules_extra_package %{?1:%{1}} %{!?{-n}:%{1}}%{?{-n}:%{-n*}} %{-m:%{-m}}}\
%if %{-m:0}%{!-m:1}\
%{expand:%%kernel_modules_internal_package %{?1:%{1}} %{!?{-n}:%{1}}%{?{-n}:%{-n*}}}\
%if 0%{!?fedora:1}\
%{expand:%%kernel_modules_partner_package %{?1:%{1}} %{!?{-n}:%{1}}%{?{-n}:%{-n*}}}\
%endif\
%{expand:%%kernel_debuginfo_package %{?1:%{1}}}\
%endif\
%if "%{1}" == "rt" || "%{1}" == "rt-debug"\
%{expand:%%kernel_kvm_package %{?1:%{1}}} %{!?{-n}:%{1}}%{?{-n}:%{-n*}}}\
%else \
%if %{with_efiuki}\
%package %{?1:%{1}-}uki-virt\
Summary: %{variant_summary} unified kernel image for virtual machines\
Provides: installonlypkg(kernel)\
Provides: kernel-%{?1:%{1}-}uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel%{?1:-%{1}}-modules-core-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires(pre): %{kernel_prereq}\
Requires(pre): systemd\
%endif\
%endif\
%if %{with_gcov}\
%{expand:%%kernel_gcov_package %{?1:%{1}}}\
%endif\
%{nil}

#
# This macro creates a kernel-<subpackage>-modules-partner package.
#	%%kernel_modules_partner_package <subpackage> <pretty-name>
#
%define kernel_modules_partner_package() \
%package %{?1:%{1}-}modules-partner\
Summary: Extra kernel modules to match the %{?2:%{2} }kernel\
Group: System Environment/Kernel\
Provides: kernel%{?1:-%{1}}-modules-partner-%{_target_cpu} = %{specrpmversion}-%{release}\
Provides: kernel%{?1:-%{1}}-modules-partner-%{_target_cpu} = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: kernel%{?1:-%{1}}-modules-partner = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: installonlypkg(kernel-module)\
Provides: kernel%{?1:-%{1}}-modules-partner-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel%{?1:-%{1}}-modules-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel%{?1:-%{1}}-modules-core-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
AutoReq: no\
AutoProv: yes\
%description %{?1:%{1}-}modules-partner\
This package provides kernel modules for the %{?2:%{2} }kernel package for Red Hat partners usage.\
%{nil}

# Now, each variant package.
%if %{with_zfcpdump}
%define variant_summary The Linux kernel compiled for zfcpdump usage
%kernel_variant_package -o zfcpdump
%description zfcpdump-core
The kernel package contains the Linux kernel (vmlinuz) for use by the
zfcpdump infrastructure.
# with_zfcpdump
%endif

%if %{with_arm64_16k_base}
%define variant_summary The Linux kernel compiled for 16k pagesize usage
%kernel_variant_package 16k
%description 16k-core
The kernel package contains a variant of the ARM64 Linux kernel using
a 16K page size.
%endif

%if %{with_arm64_16k} && %{with_debug}
%define variant_summary The Linux kernel compiled with extra debugging enabled
%if !%{debugbuildsenabled}
%kernel_variant_package -m 16k-debug
%else
%kernel_variant_package 16k-debug
%endif
%description 16k-debug-core
The debug kernel package contains a variant of the ARM64 Linux kernel using
a 16K page size.
This variant of the kernel has numerous debugging options enabled.
It should only be installed when trying to gather additional information
on kernel bugs, as some of these options impact performance noticably.
%endif

%if %{with_arm64_64k_base}
%define variant_summary The Linux kernel compiled for 64k pagesize usage
%kernel_variant_package 64k
%description 64k-core
The kernel package contains a variant of the ARM64 Linux kernel using
a 64K page size.
%endif

%if %{with_arm64_64k} && %{with_debug}
%define variant_summary The Linux kernel compiled with extra debugging enabled
%if !%{debugbuildsenabled}
%kernel_variant_package -m 64k-debug
%else
%kernel_variant_package 64k-debug
%endif
%description 64k-debug-core
The debug kernel package contains a variant of the ARM64 Linux kernel using
a 64K page size.
This variant of the kernel has numerous debugging options enabled.
It should only be installed when trying to gather additional information
on kernel bugs, as some of these options impact performance noticably.
%endif

%if %{with_debug} && %{with_realtime}
%define variant_summary The Linux PREEMPT_RT kernel compiled with extra debugging enabled
%kernel_variant_package rt-debug
%description rt-debug-core
The kernel package contains the Linux kernel (vmlinuz), the core of any
Linux operating system.  The kernel handles the basic functions
of the operating system:  memory allocation, process allocation, device
input and output, etc.

This variant of the kernel has numerous debugging options enabled.
It should only be installed when trying to gather additional information
on kernel bugs, as some of these options impact performance noticably.
%endif

%if %{with_realtime_base}
%define variant_summary The Linux kernel compiled with PREEMPT_RT enabled
%kernel_variant_package rt
%description rt-core
This package includes a version of the Linux kernel compiled with the
PREEMPT_RT real-time preemption support
%endif

%if %{with_up} && %{with_debug}
%if !%{debugbuildsenabled}
%kernel_variant_package -m debug
%else
%kernel_variant_package debug
%endif
%description debug-core
The kernel package contains the Linux kernel (vmlinuz), the core of any
Linux operating system.  The kernel handles the basic functions
of the operating system:  memory allocation, process allocation, device
input and output, etc.

This variant of the kernel has numerous debugging options enabled.
It should only be installed when trying to gather additional information
on kernel bugs, as some of these options impact performance noticably.
%endif

%if %{with_up_base}
# And finally the main -core package

%define variant_summary The Linux kernel
%kernel_variant_package
%description core
The kernel package contains the Linux kernel (vmlinuz), the core of any
Linux operating system.  The kernel handles the basic functions
of the operating system: memory allocation, process allocation, device
input and output, etc.
%endif

%if %{with_up} && %{with_debug} && %{with_efiuki}
%description debug-uki-virt
Prebuilt debug unified kernel image for virtual machines.
%endif

%if %{with_up_base} && %{with_efiuki}
%description uki-virt
Prebuilt default unified kernel image for virtual machines.
%endif

%if %{with_ipaclones}
%kernel_ipaclones_package
%endif

%prep
# do a few sanity-checks for --with *only builds
%if %{with_baseonly}
%if !%{with_up}
echo "Cannot build --with baseonly, up build is disabled"
exit 1
%endif
%endif

# more sanity checking; do it quietly
if [ "%{patches}" != "%%{patches}" ] ; then
  for patch in %{patches} ; do
    if [ ! -f $patch ] ; then
      echo "ERROR: Patch  ${patch##/*/}  listed in specfile but is missing"
      exit 1
    fi
  done
fi 2>/dev/null

patch_command='git --work-tree=. apply'
ApplyPatch()
{
  local patch=$1
  shift
  if [ ! -f $RPM_SOURCE_DIR/$patch ]; then
    exit 1
  fi
  if ! grep -E "^Patch[0-9]+: $patch\$" %{_specdir}/${RPM_PACKAGE_NAME}.spec ; then
    if [ "${patch:0:8}" != "patch-%{kversion}." ] ; then
      echo "ERROR: Patch  $patch  not listed as a source patch in specfile"
      exit 1
    fi
  fi 2>/dev/null
  case "$patch" in
  *.bz2) bunzip2 < "$RPM_SOURCE_DIR/$patch" | $patch_command ${1+"$@"} ;;
  *.gz)  gunzip  < "$RPM_SOURCE_DIR/$patch" | $patch_command ${1+"$@"} ;;
  *.xz)  unxz    < "$RPM_SOURCE_DIR/$patch" | $patch_command ${1+"$@"} ;;
  *) $patch_command ${1+"$@"} < "$RPM_SOURCE_DIR/$patch" ;;
  esac
}

# don't apply patch if it's empty
ApplyOptionalPatch()
{
  local patch=$1
  shift
  if [ ! -f $RPM_SOURCE_DIR/$patch ]; then
    exit 1
  fi
  local C=$(wc -l $RPM_SOURCE_DIR/$patch | awk '{print $1}')
  if [ "$C" -gt 9 ]; then
    ApplyPatch $patch ${1+"$@"}
  fi
}

%setup -q -n kernel-%{tarfile_release} -c
mv linux-%{tarfile_release} linux-%{KVERREL}

cd linux-%{KVERREL}
cp -a %{SOURCE1} .

%if !%{nopatches}

ApplyOptionalPatch patch-%{patchversion}-redhat.patch





ApplyOptionalPatch 0001-Added-dts-and-defconfig-files-modified-8250_dwlib.c-.patch
ApplyOptionalPatch 0002-Added-clk-reset-driver.patch
ApplyOptionalPatch 0003-feat-dma-coherent-noncoherent-Support-dma-coherent-n.patch
ApplyOptionalPatch 0004-feat-eswin-memory-Added-eswin-memory-related-changes.patch
ApplyOptionalPatch 0005-feat-SMMU-support-Support-SMMU.patch
ApplyOptionalPatch 0006-feat-eswin-mailbox-Added-eswin-mailbox-related-chang.patch
ApplyOptionalPatch 0007-feat-eswin-pinctrl-Added-eswin-pinctrl-related-chang.patch
ApplyOptionalPatch 0008-feat-Add-support-for-ethernet-driver.patch
ApplyOptionalPatch 0009-feat-EVB-A2-dts-pcie-Added-EVB-A2-dts.patch
ApplyOptionalPatch 0010-feat-CMA-Select-CONFIG_CMA-and-CONFIG_DMA_CMA.patch
ApplyOptionalPatch 0011-feat-bootspi-Add-bootspi-flash-driver.patch
ApplyOptionalPatch 0012-feat-noc-Add-noc-driver.patch
ApplyOptionalPatch 0013-feat-Add-VO-support-for-linux-6.6.patch
ApplyOptionalPatch 0014-feat-Add-emmc-and-sdio-driver.patch
ApplyOptionalPatch 0015-fix-vo-add-dma-noncoherent-for-video-ouput-device.patch
ApplyOptionalPatch 0016-feat-support-eswin-dwc3-usb.patch
ApplyOptionalPatch 0017-feat-support-ddr-ecc-check-and-report.patch
ApplyOptionalPatch 0018-feat-Porting-eswin-audio-to-6.6-kernel.patch
ApplyOptionalPatch 0019-feat-support-mpq8785-to-set-npu-voltage.patch
ApplyOptionalPatch 0020-feat-Add-dma-driver.patch
ApplyOptionalPatch 0021-feat-Select-emmc-sdio-wireless-drivers-by-default.patch
ApplyOptionalPatch 0022-feat-spram-Treat-spram-as-part-of-the-sys-memory-spa.patch
ApplyOptionalPatch 0023-feat-cma-heap-Select-CONFIG_DMABUF_HEAPS_CMA.patch
ApplyOptionalPatch 0024-feat-sata-driver-to-linux-6.6.patch
ApplyOptionalPatch 0025-feat-add-support-pac1934-to-get-som-voltage-info.patch
ApplyOptionalPatch 0026-fix-modify-ina226-addr-and-hold-time.patch
ApplyOptionalPatch 0027-fix-IOMMU-Add-ARCH_HAS_TEARDOWN_DMA_OPS.patch
ApplyOptionalPatch 0028-feat-Porting-hdmi-driver-to-linux-6.6.patch
ApplyOptionalPatch 0029-feat-DRM-Add-DSI-support-for-linux-6.6.patch
ApplyOptionalPatch 0030-feat-add-fan-rtc-wdt-dw-spi-pwm.patch
ApplyOptionalPatch 0031-feat-pvt_sensors-driver-to-linux-6.6.patch
ApplyOptionalPatch 0032-refactor-khandle-dsp-subsys-drv.patch
ApplyOptionalPatch 0033-fix-modify-fan-control-and-read-fan-speed.patch
ApplyOptionalPatch 0034-fix-Add-rtc-pcf8573-driver-in-win2030_defconfig.patch
ApplyOptionalPatch 0035-fix-add-sysfs-in-pac1934-to-set-update-interval.patch
ApplyOptionalPatch 0036-feat-llc_spram-set-npu-default-freq-to-1.5G.patch
ApplyOptionalPatch 0037-fix-llc_spram-Removed-linux-version-check.patch
ApplyOptionalPatch 0038-perf-update-dma-pwm-timer-driver.patch
ApplyOptionalPatch 0039-fix-dsp-dma-ranges-buf-fix.patch
ApplyOptionalPatch 0040-refactor-remove-useless-code-in-emmc-sd-driver.patch
ApplyOptionalPatch 0041-fix-distinguish-built-in-RTC-and-PCF-RTC.patch
ApplyOptionalPatch 0042-fix-adapt-linux6.6.patch
ApplyOptionalPatch 0043-fix-delete-useless-audio-code.patch
ApplyOptionalPatch 0044-fix-add-label-for-all-hwmon.patch
ApplyOptionalPatch 0045-feat-add-dirver-for-fsub303-to-support-type-c.patch
ApplyOptionalPatch 0046-chore-es_buddy-Memory-workaround-for-g2d-hardware-pr.patch
ApplyOptionalPatch 0047-feat-ISP-Add-VI-dev-to-linux-6.6.patch
ApplyOptionalPatch 0048-fix-add-enable-disable-for-hdcp1x.patch
ApplyOptionalPatch 0049-fix-optimize-SDHCI-driver.patch
ApplyOptionalPatch 0050-feat-Support-tca6416-for-csi-reset.patch
ApplyOptionalPatch 0051-refactor-Implement-pcie-intx-and-pmu-dtsi-config.patch
ApplyOptionalPatch 0052-fix-modify-LSB-for-mpq8785-to-1mdegress-LSB.patch
ApplyOptionalPatch 0053-fix-optimize-SDHCI-driver-tuning.patch
ApplyOptionalPatch 0054-feat-bootspi-flash-support-write-proection.patch
ApplyOptionalPatch 0055-fix-spi-del-dma.patch
ApplyOptionalPatch 0056-fix-vo-Fix-cursor-layer-resolution.patch
ApplyOptionalPatch 0057-fix-Solving-HDMI-driver-compilation-issue.patch
ApplyOptionalPatch 0058-feat-add-hifive-premier-550-dts.patch
ApplyOptionalPatch 0059-fix-BootSpi-contronller-check-flash-status-register.patch
ApplyOptionalPatch 0060-feat-dts-add-apply_npu_high_freq-in-dts.patch
ApplyOptionalPatch 0061-fix-add-audio-sound-card-name.patch
ApplyOptionalPatch 0062-fix-set-npu-default-freq-to-1.5G.patch
ApplyOptionalPatch 0063-fix-delete-extra-print.patch
ApplyOptionalPatch 0064-fix-support-power-managemnt.patch
ApplyOptionalPatch 0065-fix-es-buddy-add-spin-lock.patch
ApplyOptionalPatch 0066-fix-Delete-HDCP1.4-authentication-key.patch
ApplyOptionalPatch 0067-fix-fix-the-issue-of-getting-hub-descriptor-fail.patch
ApplyOptionalPatch 0068-fix-fix-the-issue-of-USB-3.0-host-halt.patch
ApplyOptionalPatch 0069-img-gpu-kmd-migrate-from-5.17-to-6.6.patch
ApplyOptionalPatch 0070-img-gpu-kmd-remove-warning-of-flush_scheduled_work-t.patch
ApplyOptionalPatch 0071-img-gpu-kmd-update-kernel-api-of-dma_resv.patch
ApplyOptionalPatch 0072-img-gpu-kmd-update-kernel-api-dma_buf_map-to-iosys_m.patch
ApplyOptionalPatch 0073-img-gpu-kmd-update-kernel-api-register_shrinker.patch
ApplyOptionalPatch 0074-img-gpu-kmd-use-arch_sync_dma_for_device-instead-of-.patch
ApplyOptionalPatch 0075-img-gpu-kmd-fix-vm_flags-setting-issue.patch
ApplyOptionalPatch 0076-regulator-mpq8785-mpq8785_label-add-label-len-for-np.patch
ApplyOptionalPatch 0077-chore-dtb_install-in-boot.patch
ApplyOptionalPatch 0078-feat-enable-h-ext.patch
ApplyOptionalPatch 0079-ttm-disallow-cached-mapping.patch
ApplyOptionalPatch 0080-drm-eswin-fbdev-fix-es-fbdev.patch
ApplyOptionalPatch 0081-configs-remove-CONFIG_LOCALVERSION_AUTO.patch
ApplyOptionalPatch 0082-configs-enable-initrd.patch
ApplyOptionalPatch 0083-configs-enable-amd-gpu-driver.patch
ApplyOptionalPatch 0084-configs-enable-kvm.patch
ApplyOptionalPatch 0085-configs-enable-hd-audio-pci-support.patch
ApplyOptionalPatch 0086-config-enable-option-for-docker-podman.patch
ApplyOptionalPatch 0087-fix-remove-win2030-localversion.patch
ApplyOptionalPatch 0088-fix-disable-CONFIG_ESWIN_VIRTUAL_DISPLAY.patch
ApplyOptionalPatch 0089-configs-enable-CONFIG_BINFMT_MISC.patch
ApplyOptionalPatch 0090-configs-enable-CONFIG_DEBUG_FS.patch
ApplyOptionalPatch 0091-configs-enable-MEDIA_USB_SUPPORT-MEDIA_PCI_SUPPORT.patch
ApplyOptionalPatch 0092-fix-eswin-load-kvm-module-failed.patch
ApplyOptionalPatch 0093-config-enable-some-options-for-the-distribution.patch
ApplyOptionalPatch 0094-perf-dw-axi-dmac-print.patch
ApplyOptionalPatch 0095-fix-bootspi-support-power-managemnt.patch
ApplyOptionalPatch 0096-chore-change-CONFIG_DMATEST-m.patch
ApplyOptionalPatch 0097-feat-eth-ETH-support-power-management.patch
ApplyOptionalPatch 0098-feat-npu-drv-support-low-power.patch
ApplyOptionalPatch 0099-feat-emmc-sd-sdio-sdhci-support-power-management.patch
ApplyOptionalPatch 0100-feat-vo-OSD-Support-power-management.patch
ApplyOptionalPatch 0101-refactor-MMZ-vb-and-heap-MMZ-code-moved-in-kernel.patch
ApplyOptionalPatch 0102-feat-Video-Integrate-Video-driver-into-linux6.6.patch
ApplyOptionalPatch 0103-refactor-move-es_dev_buf-and-iommu_rsv-into-kernel.patch
ApplyOptionalPatch 0104-feat-pmdomain-Add-power-domain-framework-support.patch
ApplyOptionalPatch 0105-feat-DW200-Dw200-Support-power-management.patch
ApplyOptionalPatch 0106-feat-adapt-g2d-for-the-RPM-framework.patch
ApplyOptionalPatch 0107-feat-I2s-support-low-power.patch
ApplyOptionalPatch 0108-feat-PCIe-Controller-support-low-power.patch
ApplyOptionalPatch 0109-refactor-remove-1.5GHz-1.8GHz-cpu-freq.patch
ApplyOptionalPatch 0110-refactor-remove-1.5GHz-1.8GHz-cpu-freq-die1.patch
ApplyOptionalPatch 0111-fix-cpu-pll-enable-cpu-low-power-clk-when-use-it.patch
ApplyOptionalPatch 0112-feat-HDMI-support-low-power.patch
ApplyOptionalPatch 0113-feat-linux-6.6-add-npu-dsp-driver.patch
ApplyOptionalPatch 0114-feat-sd-wifi-support-power-management.patch
ApplyOptionalPatch 0115-fix-vo-clk-off-after-dc-initialized.patch
ApplyOptionalPatch 0116-fix-Fix-a-fan-duty-cycle-error.patch
ApplyOptionalPatch 0117-fix-put-power-on-if-the-interrupt-came.patch
ApplyOptionalPatch 0118-fix-check-brother-core-event-queue-empty-when-idle.patch
ApplyOptionalPatch 0119-feat-PCIe-Controller-PM-support-power-on-off.patch
ApplyOptionalPatch 0120-fix-eth-Add-tbu-power-down-when-clk-off.patch
ApplyOptionalPatch 0121-refactor-add-eic7700-defconfig-and-adjust-mmz-size.patch
ApplyOptionalPatch 0122-fix-fix-the-cpu-100-issue-when-wait-FE-idle.patch
ApplyOptionalPatch 0123-fix-fix-the-issue-of-sd-resuming-fail.patch
ApplyOptionalPatch 0124-feat-vdec-support-power-managemnt.patch
ApplyOptionalPatch 0125-feat-VE-VE-support-power-management.patch
ApplyOptionalPatch 0126-feat-add-cpu-idle-framework-support.patch
ApplyOptionalPatch 0127-fix-VE-fix-var-name-redefinition.patch
ApplyOptionalPatch 0128-feat-Add-lpcpu-driver-for-linux-6.6.patch
ApplyOptionalPatch 0129-fix-fix-some-ep-device-cannot-resume.patch
ApplyOptionalPatch 0130-fix-use-timer-500ms-to-try-gpu-idle.patch
ApplyOptionalPatch 0131-fix-fix-regulator-warning-print.patch
ApplyOptionalPatch 0132-refactor-add-vo-qos-config.patch
ApplyOptionalPatch 0133-refactor-modify-evb1-dts.patch
ApplyOptionalPatch 0134-feat-add-lpcpu-eic7700-defconfig-and-dts.patch
ApplyOptionalPatch 0135-fix-DW200-Fix-generic-pm-crash-issue.patch
ApplyOptionalPatch 0136-feat-Introduce-system-suspend-support.patch
ApplyOptionalPatch 0137-fix-DC8K-data-compressed-when-outputting-RGB.patch
ApplyOptionalPatch 0138-feat-change-idle-defconfig-from-win2030-to-eic7700.patch
ApplyOptionalPatch 0139-feat-add-single-die-of-7702-dts.patch
ApplyOptionalPatch 0140-fix-when-write-protection-config-do-runtime-resume.patch
ApplyOptionalPatch 0141-fix-signal-to-wait-the-gpu-idle.patch
ApplyOptionalPatch 0142-feat-Deselect-CONFIG_PM.patch
ApplyOptionalPatch 0143-feat-remove-nonret-cpu-idle-state.patch
ApplyOptionalPatch 0144-Revert-Merge-branch-win2030-dev-into-release-730.patch
ApplyOptionalPatch 0145-feat-Deselect-CONFIG_CPU_IDLE.patch
ApplyOptionalPatch 0146-refactor-uniform-naming-of-hifive-premier-p550.patch
ApplyOptionalPatch 0147-feat-KASAN-warnning-bootspi-region-protection.patch
ApplyOptionalPatch 0148-feat-dsi-support-set-bus-format.patch
ApplyOptionalPatch 0149-fix-AO-case-failed.patch
ApplyOptionalPatch 0150-fix-kasan-for-vc-driver.patch
ApplyOptionalPatch 0151-fix-set-i2s0-io-func-to-GPIO.patch
ApplyOptionalPatch 0152-fix-enc-opt-log-in-enc-driver.patch
ApplyOptionalPatch 0153-fix-noc-fix-kmemleak-warning.patch
ApplyOptionalPatch 0154-fix-chang-the-delayline-of-sdio0.patch
ApplyOptionalPatch 0155-fix-add-i2c-hold-time-for-aon-i2c.patch
ApplyOptionalPatch 0156-fix-enc-fix-hang-issue-of-ve-roi.patch
ApplyOptionalPatch 0157-Merge-patch-series-membarrier-riscv-Core-serializing.patch
ApplyOptionalPatch 0158-symbol-gpl-export-pud_offset-p4d_offset-symbol.patch
ApplyOptionalPatch 0159-fix-pwm-eswin-Rename-pwm_apply_state-to-pwm_apply_mi.patch
ApplyOptionalPatch 0160-riscv-Add-support-for-kernel-mode-FPU.patch
ApplyOptionalPatch 0161-riscv-Factor-out-riscv-march-y-to-a-separate-Makefil.patch
ApplyOptionalPatch 0162-drm-amd-display-Support-DRM_AMD_DC_FP-on-RISC-V.patch
ApplyOptionalPatch 0163-feat-add-eic7700_dbg_defconfig.patch
ApplyOptionalPatch 0164-feat-Disable-CONFIG_PM.patch
ApplyOptionalPatch 0165-fix-check_mc_cmdbuf_irq.patch
ApplyOptionalPatch 0166-fix-Update-the-NPU-DSP-driver-code.patch
ApplyOptionalPatch 0167-feat-Open-the-NPU-DSP-driver-module.patch
ApplyOptionalPatch 0168-style-harmonize-device-tree.patch
ApplyOptionalPatch 0169-feat-npu-drv-need-add-autoload.patch
ApplyOptionalPatch 0170-feat-Support-mmz-partition-resize.patch
ApplyOptionalPatch 0171-fix-Synchronize-configuration-from-eic7700_defconfig.patch
ApplyOptionalPatch 0172-chore-Remove-redundant-log.patch
ApplyOptionalPatch 0173-chore-Reduce-print-in-mmz_vb.patch
ApplyOptionalPatch 0174-to-je-disable-je-timeout-check.patch
ApplyOptionalPatch 0175-feat-add-cpu-volatge-adjust.patch
ApplyOptionalPatch 0176-feat-merge-DSP-DSP-NPU-SDK-driver-to-linux.patch
ApplyOptionalPatch 0177-feat-support-bluetooth.patch
ApplyOptionalPatch 0178-feat-add-trylock-for-npu-ioctl-Changelogs-add-tryloc.patch
ApplyOptionalPatch 0179-fix-HDMI-audio-only-supports-playback.patch
ApplyOptionalPatch 0180-feat-Loud-sound-occurs-for-debian-start-for-linux.patch
ApplyOptionalPatch 0181-fix-dsp-driver-need-cancel-scheduled-work.patch
ApplyOptionalPatch 0182-feat-fix-clock-pmic-noc-init-initialization-order.patch
ApplyOptionalPatch 0183-fix-Correct-word-errors-remove-unused-define.patch
ApplyOptionalPatch 0184-fix-Resolve-DSP-SMMU-error.patch
ApplyOptionalPatch 0185-fix-CPU-run-1.6GHz-without-voltage-boost-if-allowed.patch
ApplyOptionalPatch 0186-feat-decode-with-user-space-buffer.patch
ApplyOptionalPatch 0187-feat-NPU-DSP-drivers-shouldn-t-load-on-failure.patch
ApplyOptionalPatch 0188-fix-feature-pm-compiliation.patch
ApplyOptionalPatch 0189-fix-sdk-mc-linstener-thread-cannot-exit.patch
ApplyOptionalPatch 0190-feat-NPU-DSP-driver-port.patch
ApplyOptionalPatch 0191-fix-Resolve-the-i2s-driver-crash-issue.patch
ApplyOptionalPatch 0192-refactor-move-the-cipher-driver-source-code-in-to-ke.patch
ApplyOptionalPatch 0193-fix-je-access-error-occurred-when-je-stable-test.patch
ApplyOptionalPatch 0194-fix-The-wrong-dev-id-was-used-for-vcmd-release.patch
ApplyOptionalPatch 0195-feat-support-IPA-thermal-control.patch
ApplyOptionalPatch 0196-fix-fix-sata-reset.patch
ApplyOptionalPatch 0197-sync-drm-support-debugfs-control-virtual.patch
ApplyOptionalPatch 0198-fix-Solving-hdmi-display-compatibility-issues.patch
ApplyOptionalPatch 0199-fix-DSP-NPU-driver-code-compliance.patch
ApplyOptionalPatch 0200-feat-add-license-description.patch
ApplyOptionalPatch 0201-feat-NOC-driver-adapt-to-bandwidth-test.patch
ApplyOptionalPatch 0202-feat-dsp-drv-use-dsp-pool-for-flat-mem.patch
ApplyOptionalPatch 0203-feat-recover-volume-to-6dB-for-debian.patch
ApplyOptionalPatch 0204-fix-resolve-HDMI-hot-plug-compatibility-issues.patch
ApplyOptionalPatch 0205-perf-change-smmu-print-level-optimize-ccache-flush.patch
ApplyOptionalPatch 0206-fix-open-card-sleep-0.5ms-then-set-volume.patch
ApplyOptionalPatch 0207-Revert-perf-change-smmu-print-level-optimize-ccache-.patch
ApplyOptionalPatch 0208-perf-change-smmu-print-level.patch
ApplyOptionalPatch 0209-fix-Add-dsp-op-buffer-cnt.patch
ApplyOptionalPatch 0210-fix-DSP-driver-add-license-claim.patch
ApplyOptionalPatch 0211-style-Code-format-compliance-modifications.patch
ApplyOptionalPatch 0212-config-enable-tun-tap.patch
ApplyOptionalPatch 0213-config-enable-landlock.patch
ApplyOptionalPatch 0214-perf-vendor-events-riscv-Add-SiFive-P550-events.patch
ApplyOptionalPatch 0215-npu-add-es5340-support.patch
ApplyOptionalPatch 0216-dts-eswin-add-megrez-device-tree.patch
ApplyOptionalPatch 0217-dts-megrez-add-1.6GHz.patch
ApplyOptionalPatch 0218-fix-dts-megrez-audio-remove-unused-es8388.patch
ApplyOptionalPatch 0219-dts-megrez-add-pwm-fan.patch
ApplyOptionalPatch 0220-backport-riscv-optimize-ELF-relocation-function-in-r.patch
ApplyOptionalPatch 0221-configs-enable-thermal.patch
ApplyOptionalPatch 0222-fix-8250_dw-typo.patch
ApplyOptionalPatch 0223-Revert-sync-drm-support-debugfs-control-virtual.patch
ApplyOptionalPatch 0224-enable-CONFIG_CRYPTO_DEV_ESWIN_EIC770x-y.patch
ApplyOptionalPatch 0225-sync-sync-thermal-config-for-win2030.patch
ApplyOptionalPatch 0226-Use-.NOTINTERMEDIATE-or-.SECONDARY-based-on-make-ver.patch
ApplyOptionalPatch 0227-gpu-img-Replace-deprecated-functions.patch
ApplyOptionalPatch 0228-drivers-gpu-img-Resolve-compilation-warnings.patch
ApplyOptionalPatch 0229-WIN2030-16633-feat-updata-gpu-kernel-driver-to-ddk24.patch
ApplyOptionalPatch 0230-drivers-kvm-vcpu-Disabled-writing-HENVCFG-reg.patch
ApplyOptionalPatch 0231-HACK-reject-sscofpmf-for-kvm.patch
ApplyOptionalPatch 0232-drivers-eswin-fix-out-of-tree-compilation.patch
ApplyOptionalPatch 0233-riscv-dts-eswin-add-Pine64-StarPro64.patch
ApplyOptionalPatch 0234-config-add-intel-wifi-rtl.patch
ApplyOptionalPatch 0235-wireless-add-BCMHD-ap12275.patch
ApplyOptionalPatch 0236-configs-enable-CONFIG_BCMDHD_SDIO_IRQ.patch
ApplyOptionalPatch 0237-fix-add-irq-reset-gpio-for-aw3155.patch
ApplyOptionalPatch 0238-feat-sdhci-driver-add-dump_vendor_regs-function.patch
ApplyOptionalPatch 0239-fix-fix-the-issue-of-emmc-cmd-timeout.patch
ApplyOptionalPatch 0240-fix-remove-csr-clk-from-eth-driver.patch
ApplyOptionalPatch 0241-feat-add-audio-proc-mutex.patch
ApplyOptionalPatch 0242-feat-skip-the-user-memory-cache-flush.patch
ApplyOptionalPatch 0243-feat-modify-the-audio-proc-license-statement.patch
ApplyOptionalPatch 0244-WIN2030-14758-feat-Add-eic7702-evb-a1.dts.patch
ApplyOptionalPatch 0245-WIN2030-16098-ci-dw200-support-d2d.patch
ApplyOptionalPatch 0246-WIN2030-16132-feat-run-on-the-specify-die.patch
ApplyOptionalPatch 0247-WIN2030-16132-feat-enc-new-feature-of-d2d-for-enc-dr.patch
ApplyOptionalPatch 0248-WIN2030-16070-feat-add-eic7x-pinctrl-driver.patch
ApplyOptionalPatch 0249-WIN2030-13899-fix-adapt-sdhci-driver-to-eic7702.patch
ApplyOptionalPatch 0250-WIN2030-16035-refactor-support-eic7702-evb.patch
ApplyOptionalPatch 0251-WIN2030-16122-feat-e31-support-dual-die-Changelogs.patch
ApplyOptionalPatch 0252-WIN2030-15907-feat-audio-adaptation-for-dual-die.patch
ApplyOptionalPatch 0253-WIN2030-16289-feat-support-npu-dual-die.patch
ApplyOptionalPatch 0254-WIN2030-16284-fix-adapt-pinctrl-driver-for-eic7x.patch
ApplyOptionalPatch 0255-WIN2030-16098-ci-dc8k-drm-driver-adapt-d2d.patch
ApplyOptionalPatch 0256-WIN2030-16286-feat-2d-support-d2d-feature.patch
ApplyOptionalPatch 0257-WIN2030-16035-feat-eth-Adaption-for-ethernet-d2d.patch
ApplyOptionalPatch 0258-WIN2030-16035-feat-vdec-support-d2d.patch
ApplyOptionalPatch 0259-WIN2030-14758-fix-dma_numa_cma_reserve-failed.patch
ApplyOptionalPatch 0260-WIN2030-16035-fix-enc-dec-fix-dma-heap-error-for-d2d.patch
ApplyOptionalPatch 0261-WIN2030-16098-fix-Drm-driver-add-component-failed-is.patch
ApplyOptionalPatch 0262-WIN2030-16287-feat-support-es5340-for-npu-modify-ina.patch
ApplyOptionalPatch 0263-WIN2030-16286-feat-fix-2d-cannot-alloc-die0-cma-addr.patch
ApplyOptionalPatch 0264-WIN2030-16287-feat-suppor-tmp102-to-get-board-temper.patch
ApplyOptionalPatch 0265-WIN2030-16035-feat-Add-undefined-device-information.patch
ApplyOptionalPatch 0266-WIN2030-16035-feat-uninstall-the-vdec-driver-for-d2d.patch
ApplyOptionalPatch 0267-WIN2030-16287-feat-support-touchscreen-gt911.patch
ApplyOptionalPatch 0268-WIN2030-16233-feat-hdmi-hdcp-driver-adapt-d2d.patch
ApplyOptionalPatch 0269-WIN2030-16233-fix-resolve-hdcp-compilation-issue.patch
ApplyOptionalPatch 0270-WIN2030-14758-fix-venc-driver-iova-allocation-for-ve.patch
ApplyOptionalPatch 0271-WIN2030-14758-fix-vdec-driver-iova-allocation-for-vd.patch
ApplyOptionalPatch 0272-WIN2030-16035-refactor-implement-d2d-interrupts-moni.patch
ApplyOptionalPatch 0273-WIN2030-16139-fix-optimize-hae-blit-with-stall-on-CP.patch
ApplyOptionalPatch 0274-WIN2030-16271-feat-add-delay_work-for-d2d-s-adaptati.patch
ApplyOptionalPatch 0275-WIN2030-16572-feat-dsp-move-dual-die-support-to-linu.patch
ApplyOptionalPatch 0276-WIN2030-16576-feat-npu-drv-support-dual-die-move-to-.patch
ApplyOptionalPatch 0277-WIN2030-16445-fix-Resolve-DSP-NPU-driver-compilation.patch
ApplyOptionalPatch 0278-WIN2030-16035-refactor-Add-numa-node-id-of-Die0-s-cp.patch
ApplyOptionalPatch 0279-WIN2030-16035-refactor-Support-ECC-mode.patch
ApplyOptionalPatch 0280-WIN2030-16035-fix-Fixbug-double-ddr-controllers-driv.patch
ApplyOptionalPatch 0281-WIN2030-15078-fix-add-irq-reset-gpio-for-aw3155-in-7.patch
ApplyOptionalPatch 0282-WIN2030-15365-fix-porting-modify-for-dual-e31-Change.patch
ApplyOptionalPatch 0283-WIN2030-16657-fix-jenc-enc-32k-jpeg-hang.patch
ApplyOptionalPatch 0284-WIN2030-16445-fix-resolve-the-issue-of-DMA-interrupt.patch
ApplyOptionalPatch 0285-WIN2030-15186-fix-Fan-at-maximum-speed.patch
ApplyOptionalPatch 0286-WIN2030-15186-fix-fix-slow-command-id-error.patch
ApplyOptionalPatch 0287-WIN2030-16035-refactor-remove-ecc-range-from-7702-ev.patch
ApplyOptionalPatch 0288-WIN2030-16286-fix-add-the-idle-timer-delay-from-500m.patch
ApplyOptionalPatch 0289-WIN2030-16671-fix-drm-add-VIRTUAL-on-7702-board-Chan.patch
ApplyOptionalPatch 0290-WIN2030-16286-fix-modify-license-information.patch
ApplyOptionalPatch 0291-WIN2030-14758-refactor-refact-split-dmabuf.patch
ApplyOptionalPatch 0292-WIN2030-16664-fix-modify-machine-model-of-7702.patch
ApplyOptionalPatch 0293-WIN2030-15186-fix-change-voltage-of-7702-npu-to-1.08.patch
ApplyOptionalPatch 0294-WIN2030-16664-refactor-add-evb-a3-dts-and-platform-m.patch
ApplyOptionalPatch 0295-WIN2030-14758-fix-split-dmabuf.patch
ApplyOptionalPatch 0296-WIN2030-16678-fix-add-hsp-clock-for-usb.patch
ApplyOptionalPatch 0297-Revert-WIN2030-16678-fix-add-hsp-clock-for-usb.patch
ApplyOptionalPatch 0298-WIN2030-16678-fix-add-hsp-clock-for-usb.patch
ApplyOptionalPatch 0299-WIN2030-16668-feat-dump-multi-dsp-input-output.patch
ApplyOptionalPatch 0300-dts-sync-eic7x-device-tree.patch
ApplyOptionalPatch 0301-configs-builtin-ESWIN_IOMMU_RSV.patch
ApplyOptionalPatch 0302-configs-remove-LOCALVERSION-for-eic7702.patch
ApplyOptionalPatch 0303-debian-linux-image-provide-wireguard-modules.patch
ApplyOptionalPatch 0304-package-add-linux-tools.patch
ApplyOptionalPatch 0305-img-AXM-8-258-not-support-DRIVER_MODESET.patch
ApplyOptionalPatch 0306-dts-enable-7702-d1_gpu.patch
ApplyOptionalPatch 0307-eic7700-megrez-add-opp-table-for-1.5G-1.8G.patch
ApplyOptionalPatch 0308-clk-eswin-add-force-1.8ghz-option.patch
ApplyOptionalPatch 0309-dts-eic770x-megrez-add-force-1.8Ghz.patch
ApplyOptionalPatch 0310-megrez-add-disable-wp-broken-cd-in-sdio.patch
ApplyOptionalPatch 0311-eth-eswin-stmmac-disable-iommu.patch
ApplyOptionalPatch 0312-configs-eic7702-add-initrd-support.patch
ApplyOptionalPatch 0313-config-eic770x-cpufreq-governor-performance-as-defau.patch
ApplyOptionalPatch 0314-megrez-support-rtc-m41t11.patch
ApplyOptionalPatch 0315-milkv-megrez-fix-sd-card-delay_code.patch
ApplyOptionalPatch 0316-riscv-dts-eswin-Add-1.8G-support-for-StarPro64.patch
ApplyOptionalPatch 0317-WIN2030-15704-feat-Add-devfreq-support.patch
ApplyOptionalPatch 0318-WIN2030-15754-feat-VI-dw200-add-devfreq-support.patch
ApplyOptionalPatch 0319-WIN2030-16526-feat-g2d-add-devfreq-support.patch
ApplyOptionalPatch 0320-WIN2030-16515-feat-venc-venc-add-devfreq-support.patch
ApplyOptionalPatch 0321-WIN2030-16532-feat-vdec-add-devfreq-support.patch
ApplyOptionalPatch 0322-WIN2030-15704-feat-Centralize-the-OOP-table.patch
ApplyOptionalPatch 0323-WIN2030-15704-fix-npu-power-off-when-npu-sleep.patch
ApplyOptionalPatch 0324-WIN2030-16551-feat-npu-drv-support-device-frequency.patch
ApplyOptionalPatch 0325-WIN2030-16578-fix-npu-opp-dts-node-modify.patch
ApplyOptionalPatch 0326-WIN2030-16230-feat-audio-add-sof-func.patch
ApplyOptionalPatch 0327-WIN2030-16445-fix-adjust-HDMI-phy-voltage.patch
ApplyOptionalPatch 0328-WIN2030-15365-fix-remove-error-message-when-try-lock.patch
ApplyOptionalPatch 0329-WIN2030-14758-feat-Add-API-for-remapping-malloc-buff.patch
ApplyOptionalPatch 0330-WIN2030-16445-fix-audio-driver-add-24-bits-support.patch
ApplyOptionalPatch 0331-WIN2030-16740-feat-support-z530-board.patch
ApplyOptionalPatch 0332-WIN2030-16760-feat-adapt-eth-driver-to-board-z530.patch
ApplyOptionalPatch 0333-WIN2030-16445-fix-fix-the-issue-of-audio-recording.patch
ApplyOptionalPatch 0334-WIN2030-16445-fix-NPU-driver-add-switch-for-perf-fun.patch
ApplyOptionalPatch 0335-WIN2030-16445-fix-DSP-driver-add-switch-for-perf-fun.patch
ApplyOptionalPatch 0336-WIN2030-16760-feat-modify-sdio-s-delay-to-adapt-to-z.patch
ApplyOptionalPatch 0337-WIN2030-16445-fix-fix-the-issue-of-no-pcm-node-on-di.patch
ApplyOptionalPatch 0338-WIN2030-14758-feat-add-interleave-dts.patch
ApplyOptionalPatch 0339-WIN2030-16412-feat-DMA-memcopy-kernel-driver.patch
ApplyOptionalPatch 0340-WIN2030-16810-fix-npu-devfeq-bug-fix.patch
ApplyOptionalPatch 0341-WIN2030-16733-feat-audio-perf-for-rtc-processing.patch
ApplyOptionalPatch 0342-WIN2030-16812-feat-hdmi-support-2880x1800-90-output.patch
ApplyOptionalPatch 0343-WIN2030-16813-chore-disable-IPA-adjust-with-target.patch
ApplyOptionalPatch 0344-WIN2030-16816-fix-fix-the-DSP-issue-of-perf-function.patch
ApplyOptionalPatch 0345-WIN2030-16831-fix-Delete-HDMI-Audio-error-printing.patch
ApplyOptionalPatch 0346-WIN2030-16760-feat-adapt-eth-dly-params-to-7702-inte.patch
ApplyOptionalPatch 0347-WIN2030-14758-feat-Select-cipher-as-default.patch
ApplyOptionalPatch 0348-WIN2030-16550-fix-7702-interleave-can-not-display-is.patch
ApplyOptionalPatch 0349-WIN2030-16412-feat-change-mode-0660.patch
ApplyOptionalPatch 0350-WIN2030-16848-fix-buffer-overflow-by-print-info.patch
ApplyOptionalPatch 0351-WIN2030-16797-fix-Resolve-the-issue-of-abnormal-stac.patch
ApplyOptionalPatch 0352-WIN2030-16860-feat-fix-96k-palyback-error.patch
ApplyOptionalPatch 0353-WIN2030-16832-feat-fix-bug-for-z530-reboot-Strange-n.patch
ApplyOptionalPatch 0354-WIN2030-16857-fix-dsp-pm-devfreq-bug-fix.patch
ApplyOptionalPatch 0355-WIN2030-14758-feat-clk-support-set-default-cpu-freq.patch
ApplyOptionalPatch 0356-WIN2030-16883-fix-npu-die1-clock-miss.patch
ApplyOptionalPatch 0357-WIN2030-16692-fix-improve-numa-node-id-of-each-modul.patch
ApplyOptionalPatch 0358-WIN2030-16746-feat-support-7700d314-and-7700s314.patch
ApplyOptionalPatch 0359-dts-eswin-rename-d0_cpu_opp_table-to-cpu_opp_table.patch
ApplyOptionalPatch 0360-npu-sync-1230-eswin-code.patch
ApplyOptionalPatch 0361-vvcam_dwe_driver-sync-eswin-20241230-code.patch
ApplyOptionalPatch 0362-dts-sync-eswin-gmac0-1-config.patch
ApplyOptionalPatch 0363-configs-eswin-add-DEVFREQ_GOV_-PERFORMANCE-POWERSAVE.patch
ApplyOptionalPatch 0364-dts-eswin-adjust-memory-node-order.patch
ApplyOptionalPatch 0365-WIN2030-14758-feat-L3-cache-flush-all.patch
ApplyOptionalPatch 0366-WIN2030-14758-fix-cipher-Add-tbus-property-for-ciphe.patch
ApplyOptionalPatch 0367-WIN2030-16898-feat-revert-reboot-generate-noise-bug.patch
ApplyOptionalPatch 0368-WIN2030-16701-fix-die1-uart-not-inited-use-uart0-bot.patch
ApplyOptionalPatch 0369-WIN2030-16708-fix-Fix-squeezenet-bug.patch
ApplyOptionalPatch 0370-WIN2030-16550-feat-Differentiate-output-devices-for-.patch
ApplyOptionalPatch 0371-WIN2030-16550-fix-Dewarp-pm-devfreq-bug-fix.patch
ApplyOptionalPatch 0372-WIN2030-16607-feat-adapt-new-eth-params-to-7702-evb.patch
ApplyOptionalPatch 0373-WIN2030-16949-fix-resolve-HDMI-driver-memory-leak-is.patch
ApplyOptionalPatch 0374-WIN2030-15186-feat-support-tps549d22-amd-tmp102-in-7.patch
ApplyOptionalPatch 0375-WIN2030-16550-perf-Optimize-dma-performance.patch
ApplyOptionalPatch 0376-WIN2030-16501-fix-Add-vi-config-TBU.patch
ApplyOptionalPatch 0377-WIN2030-16686-feat-add-dma-channel-device-filter.patch
ApplyOptionalPatch 0378-WIN2030-16910-feat-add-numa-support-for-770x.patch
ApplyOptionalPatch 0379-WIN2030-16969-fix-i2s-binding-DMA-channels.patch
ApplyOptionalPatch 0380-WIN2030-16919-feat-Apply-numa-early-node-patch-from-.patch
ApplyOptionalPatch 0381-WIN2030-16919-fix-d2d-cpu-volatge-opp-table-support.patch
ApplyOptionalPatch 0382-WIN2030-16919-fix-select-HAVE_SETUP_PER_CPU_AREA-if-.patch
ApplyOptionalPatch 0383-WIN2030-16962-feat-enable-dual-4K-display-for-Xorg.patch
ApplyOptionalPatch 0384-WIN2030-16686-feat-support-memcp-for-7702.patch
ApplyOptionalPatch 0385-WIN2030-17015-fix-fix-the-issue-of-44.1k-audio-playb.patch
ApplyOptionalPatch 0386-WIN2030-16900-feature-support-sbc-display.patch
ApplyOptionalPatch 0387-WIN2030-16891-fix-llc-drv-add-set-npu-default-voltag.patch
ApplyOptionalPatch 0388-WIN2030-16900-fix-Close-the-dsi-config-in-default-.d.patch
ApplyOptionalPatch 0389-WIN2030-16813-fix-adjust-critical-temperature.patch
ApplyOptionalPatch 0390-WIN2030-16813-fix-corrected-critical-temperature.patch
ApplyOptionalPatch 0391-WIN2030-14758-feat-Dump-tbu-attached-device-list.patch
ApplyOptionalPatch 0392-WIN2030-17068-fix-dsp-drv-mem-leak.patch
ApplyOptionalPatch 0393-WIN2030-17055-feat-npu-set-voltage-modify.patch
ApplyOptionalPatch 0394-WIN2030-16872-feat-hdmi-driver-adapt-2.2-2.8k-BOE-sc.patch
ApplyOptionalPatch 0395-WIN2030-14758-perf-Improve-GPU-mmu-operation-and-sch.patch
ApplyOptionalPatch 0396-WIN2030-17070-fix-dsp-drv-module-refcnt-problem.patch
ApplyOptionalPatch 0397-WIN2030-16980-fix-Dvb-drm-virtual-debugfs-node-reg.patch
ApplyOptionalPatch 0398-WIN2030-14758-fix-Bug-introduced-by-Improve-GPU-mmu.patch
ApplyOptionalPatch 0399-WIN2030-16409-fix-fixed-dsp-dmabuf-issue-Changelogs-.patch
ApplyOptionalPatch 0400-WIN2030-17055-feat-npu-set-voltage-modify.patch
ApplyOptionalPatch 0401-WIN2030-16412-feat-Optimize-dma-channel-request.patch
ApplyOptionalPatch 0402-fix-power-down-all-tbus-at-start-up.patch
ApplyOptionalPatch 0403-fix-sifive-ccache_flush64_range.patch
ApplyOptionalPatch 0404-iommu-eswin-sync-remove-internal-arguments-from-of_p.patch
ApplyOptionalPatch 0405-config-sync-from-eic7700_defconfig.patch
ApplyOptionalPatch 0406-iommu-eswin-lower-the-priority-of-TBU-dump.patch
ApplyOptionalPatch 0407-star64pro-megrez-fix-npu-supply-for-npu-init.patch
ApplyOptionalPatch 0408-fix-Dvb-and-z530-boot-failed-issue.patch
ApplyOptionalPatch 0409-feature-Add-eic770x-OTP-driver.patch
ApplyOptionalPatch 0410-feat-reset-driver-fit-for-upstream.patch
ApplyOptionalPatch 0411-feat-add-npu-usage-Changelogs.patch
ApplyOptionalPatch 0412-fix-2d-kernel-stack-warning-after-reboot.patch
ApplyOptionalPatch 0413-feat-clk-driver-fit-for-upstream.patch
ApplyOptionalPatch 0414-feat-modify-npu-dts-voltage.patch
ApplyOptionalPatch 0415-fix-Solve-no-power-of-tp549d22-when-cold-boot.patch
ApplyOptionalPatch 0416-fix-dambuf-helper-get-the-mutex-while-operating-on-t.patch
ApplyOptionalPatch 0417-fix-D314-sdio-delay_code.patch
ApplyOptionalPatch 0418-fix-dambuf-helper-fix-bug-of-heap-object-release.patch
ApplyOptionalPatch 0419-fix-do-not-print-message-when-failed-mem.patch
ApplyOptionalPatch 0420-fix-eswin-ai-dsp-fix-gcc-14-build-error.patch
ApplyOptionalPatch 0421-config-fs-enable-xfs-gfs-f2fs-zonefs-for-eic7700x.patch
ApplyOptionalPatch 0422-config-drm-nouveau-as-module-for-eic7700x.patch
ApplyOptionalPatch 0423-config-memory-enable-zswap.patch
ApplyOptionalPatch 0424-config-scsi-enable-scsi-config-for-eic7700x.patch
ApplyOptionalPatch 0425-config-net-enable-net-device-for-eic7700x.patch
ApplyOptionalPatch 0426-config-net-enable-net-options-for-eic7700x.patch
ApplyOptionalPatch 0427-config-net-disable-realtek-phy-for-eic7700x.patch
ApplyOptionalPatch 0428-dts-eswin-gmac-use-rgmii-txid-as-phy-mode.patch
ApplyOptionalPatch 0429-configs-eswin-enable-REALTEK_PHY-as-builtin.patch
ApplyOptionalPatch 0430-dts-eswin-p550-add-disable-wp-broken-cd.patch
ApplyOptionalPatch 0431-Revert-riscv-dts-eswin-Add-1.8G-support-for-StarPro6.patch
ApplyOptionalPatch 0432-Add-modules-required-to-run-strongswan-as-per.patch
ApplyOptionalPatch 0433-Enable-L2TP.patch
ApplyOptionalPatch 0434-drm-eswin-es_dw_hdmi-allow-non-standard-pixclk.patch
ApplyOptionalPatch 0435-drm-eswin-clean-hwcursor-state-when-enabling-the-dis.patch
ApplyOptionalPatch 0436-drm-eswin-reject-framebuffers-with-misaligned-pitch.patch
ApplyOptionalPatch 0437-feat-merge-feature-vpu7702-branch.patch
ApplyOptionalPatch 0438-fix-2d-2d-isr-interrupt-call-muetx-err.patch
ApplyOptionalPatch 0439-feat-support-osm-dts.patch
ApplyOptionalPatch 0440-fix-modify-mpq8785-critical-uint-and-es5340-lable.patch
ApplyOptionalPatch 0441-feat-support-capture-for-osm-codec.patch
ApplyOptionalPatch 0442-feat-npu-proc-add-voltage-and-frequency.patch
ApplyOptionalPatch 0443-fix-disable-cca-pvt0-and-timer1.patch
ApplyOptionalPatch 0444-fix-disable-regulator-always-on-feature.patch
ApplyOptionalPatch 0445-fix-pwm-support-inverted.patch
ApplyOptionalPatch 0446-fix-board-eic770x-adaptive-memory-size.patch
ApplyOptionalPatch 0447-feat-kernel-Add-CacheFlushAll-API-for-lib_memory.patch
ApplyOptionalPatch 0448-fix-Fix-cnoc-npu-timeout-problem.patch
ApplyOptionalPatch 0449-fix-use-rgmii-txid-as-phy-mode-for-gmac.patch
ApplyOptionalPatch 0450-feat-sbc-support-rtc-pcf85063a.patch
ApplyOptionalPatch 0451-fix-vc-opt-error-log-for-redup-interrupts.patch
ApplyOptionalPatch 0452-feature-add-7702vpu-dts.patch
ApplyOptionalPatch 0453-fix-2d-hae-disable-powersaving-for-version-0330.patch
ApplyOptionalPatch 0454-fix-modify-evb-AX-dvb-d314-eth-para-to-fit-0.9V.patch
ApplyOptionalPatch 0455-fix-npu-dsp-cpu-gpu-support-IPA.patch
ApplyOptionalPatch 0456-chore-Reduce-the-printing-in-TBU.patch
ApplyOptionalPatch 0457-fix-fix-mpq8785-enable-error-and-read-voltage-error.patch
ApplyOptionalPatch 0458-fix-venc-opt-venc-log-while-pm-resume-suspend.patch
ApplyOptionalPatch 0459-feat-support-22.01-11.025kHz.patch
ApplyOptionalPatch 0460-feat-adapt-dual-die-model.patch
ApplyOptionalPatch 0461-feat-add-e31-event-op-Changelogs.patch
ApplyOptionalPatch 0462-fix-resolve-the-dc-cursor-layer-issue.patch
ApplyOptionalPatch 0463-Revert-feature-add-7702vpu-dts.patch
ApplyOptionalPatch 0464-fix-fix-dma-buffersize.patch
ApplyOptionalPatch 0465-fix-enable-cpu-gov-userspace.patch
ApplyOptionalPatch 0466-fix-Resolve-the-issue-of-system-crashes.patch
ApplyOptionalPatch 0467-fix-fix-dma-period-size-and-cnt-to-fit-24-16-32bit.patch
ApplyOptionalPatch 0468-feat-turne-on-NPU-perf.patch
ApplyOptionalPatch 0469-fix-revert-dma-fix.patch
ApplyOptionalPatch 0470-fix-revert-dma.patch
ApplyOptionalPatch 0471-fix-dsp-pm-notifier-problem.patch
ApplyOptionalPatch 0472-fix-disable-cpu-1.4G-upper-of-evb.patch
ApplyOptionalPatch 0473-riscv-module-Optimize-PLT-GOT-entry-counting.patch
ApplyOptionalPatch 0474-riscv-module-fix-compilation-error-of-kvrealloc.patch
ApplyOptionalPatch 0475-arch-add-ARCH_HAS_KERNEL_FPU_SUPPORT.patch
ApplyOptionalPatch 0476-fix-fix-pacmsg-bug.patch
ApplyOptionalPatch 0477-feat-make-dma-period-size-under-500ms.patch
ApplyOptionalPatch 0478-fix-modify-i2c_ctrlX-mem-region-size-form-64K-to-32K.patch
ApplyOptionalPatch 0479-fix-Modify-tps549d22-enable-sequence-of-software-cfg.patch
ApplyOptionalPatch 0480-feat-support-eic7702-d560.patch
ApplyOptionalPatch 0481-feat-add-DMA-malloc-to-dmabuf-driver.patch
ApplyOptionalPatch 0482-feat-dma-memcp-add-sync-and-async-notifier.patch
ApplyOptionalPatch 0483-feat-add-memcp-offset-overflow-check.patch
ApplyOptionalPatch 0484-fix-add-disable-wp-in-sdio.patch
ApplyOptionalPatch 0485-fix-enable-usb2.0-hub.patch
ApplyOptionalPatch 0486-feat-adapt-to-vpu7702-smmu-cfg-drv.patch
ApplyOptionalPatch 0487-feat-update-dts-for-eic7702_vpu.patch
ApplyOptionalPatch 0488-feat-Merge-branch-feature-vi-into-win2030-dev.patch
ApplyOptionalPatch 0489-fix-Resolve-the-issue-of-NPU-reset.patch
ApplyOptionalPatch 0490-fix-fix-multi-process-npu-ioctl-bug.patch
ApplyOptionalPatch 0491-feat-vpu7702-smmu-cfg-modify.patch
ApplyOptionalPatch 0492-feat-eth-ETH-tuning-in-EIC7702_D560.patch
ApplyOptionalPatch 0493-fix-clear-ecc-interrupt-anytime.patch
ApplyOptionalPatch 0494-fix-pcie-check-clk-before-init.patch
ApplyOptionalPatch 0495-feat-adapt-ap6256.patch
ApplyOptionalPatch 0496-feat-to-support-both-evb-and-televpu.patch
ApplyOptionalPatch 0497-fix-fix-evb-vi-catpure-image.patch
ApplyOptionalPatch 0498-fix-pcie-tbu-error.patch
ApplyOptionalPatch 0499-feat-Export-die-idx-pin.patch
ApplyOptionalPatch 0500-feat-add-es-fand-function.patch
ApplyOptionalPatch 0501-fix-dvp2axi-kernel-warning.patch
ApplyOptionalPatch 0502-fix-modify-the-reading-method-of-rpm.patch
ApplyOptionalPatch 0503-feature-Add-kernel-eic7702-d560-interleave-dts.patch
ApplyOptionalPatch 0504-fix-NPU-enable-1.5G-performance.patch
ApplyOptionalPatch 0505-fix-VPU-model-reading-erro.patch
ApplyOptionalPatch 0506-feat-update-memory-for-mmz-and-bar2.patch
ApplyOptionalPatch 0507-feat-support-SOC-CPU-up-voltage.patch
ApplyOptionalPatch 0508-fix-fix-dc-endpoint-index.patch
ApplyOptionalPatch 0509-feat-osm-dts-add-gpio-pinctrl-script.patch
ApplyOptionalPatch 0510-fix-Revert-some-err-dts-changes-for-VI-Merge.patch
ApplyOptionalPatch 0511-feat-update-escl-linux-dependency.patch
ApplyOptionalPatch 0512-feat-sbc-support-i2c-spi.patch
ApplyOptionalPatch 0513-feature-Sync-d560-dts-config.patch
ApplyOptionalPatch 0514-fix-vpu7702-streamid-problem.patch
ApplyOptionalPatch 0515-feat-sbc-vi.patch
ApplyOptionalPatch 0516-fix-delete-warning-log.patch
ApplyOptionalPatch 0517-style-fix-the-warning-in-DTS.patch
ApplyOptionalPatch 0518-fix-sata-downspeed-issue-on-die1-debug.patch
ApplyOptionalPatch 0519-feat-Add-SD-card-detect.patch
ApplyOptionalPatch 0520-style-fix-the-warning-in-DTS.patch
ApplyOptionalPatch 0521-feat-support-dewarp-in-7702.patch
ApplyOptionalPatch 0522-fix-fix-sbc-camera-dts-warning-log.patch
ApplyOptionalPatch 0523-feat-d314-vi-support.patch
ApplyOptionalPatch 0524-fix-fix-system-hang-after-run-isp-and-sample_vps-2.patch
ApplyOptionalPatch 0525-feat-remove-v4l2_pm-in-video-open-close.patch
ApplyOptionalPatch 0526-fix-KASAN-global-out-of-bounds.patch
ApplyOptionalPatch 0527-fix-Fix-d560-interleave-cpufreq-dt-probe-fail-issue.patch
ApplyOptionalPatch 0528-fix-solve-guvcview-print-err-log.patch
ApplyOptionalPatch 0529-fix-resolve-the-issue-of-slow-fan-speed.patch
ApplyOptionalPatch 0530-fix-fix-isp-isp_media_server-error-in-debian.patch
ApplyOptionalPatch 0531-feat-d314-isp-support.patch
ApplyOptionalPatch 0532-feat-enable-ddr-ecc-for-televpu.patch
ApplyOptionalPatch 0533-config-win2030-enable-CONFIG_TASK_IO_ACCOUNTING.patch
ApplyOptionalPatch 0534-config-win2030-enable-CONFIG_FUSE_FS.patch
ApplyOptionalPatch 0535-dts-add-milkv-megrez-nx.dts.patch
ApplyOptionalPatch 0536-riscv-dts-eswin-some-starpro64-dt-changes.patch
ApplyOptionalPatch 0537-mmc-sdhci-of-eswin-ignore-bogus-small-delay-windows.patch
ApplyOptionalPatch 0538-riscv-configs-enable-Motorcomm-PHY-driver.patch
ApplyOptionalPatch 0539-riscv-dts-eswin-starpro64-tweak-GMAC0-RX-delay.patch
ApplyOptionalPatch 0540-PCI-eswin-keep-PCIe-alive-at-shutdown.patch
ApplyOptionalPatch 0541-riscv-dts-megrez-nx-fix-sata-act-led-gpio.patch
ApplyOptionalPatch 0542-ci-add-build.patch
ApplyOptionalPatch 0543-fix-fix-ubuntu-up-warning-and-terminal-lag.patch
ApplyOptionalPatch 0544-fix-disable-sdio1-by-default-for-eic7700-sbc-a1-boar.patch
ApplyOptionalPatch 0545-feat-add-new-perf-interface.patch
ApplyOptionalPatch 0546-feat-update-dts-for-eic7702_pcie.patch
ApplyOptionalPatch 0547-feat-Reserve-memory-for-version-info.patch
ApplyOptionalPatch 0548-fix-fix-SBC-MIPI-spupport-MP-test.patch
ApplyOptionalPatch 0549-feat-Reserve-memory-for-board-info.patch
ApplyOptionalPatch 0550-feature-Enable-pstore-feature.patch
ApplyOptionalPatch 0551-fix-Fix-invalid-GPIO-for-D560-gmac.patch
ApplyOptionalPatch 0552-feat-add-vpu7702_pcie_factory.dts.patch
ApplyOptionalPatch 0553-feat-use-dev_dbg-to-print-the-uart-noc-err-log.patch
ApplyOptionalPatch 0554-fix-adapt-d560-audio-input.patch
ApplyOptionalPatch 0555-feat-Reserve-memory-for-bd-info.patch
ApplyOptionalPatch 0556-feat-to-support-vpu7702-pcie-A2-card.patch
ApplyOptionalPatch 0557-fix-fix-modify-SBC-MIPI-path.patch
ApplyOptionalPatch 0558-feat-vpu-set-npu-freq-to-1G.patch
ApplyOptionalPatch 0559-feat-Enable-lpcpu-fw-load-for-vpu7702.patch
ApplyOptionalPatch 0560-fix-Open-2d-node.patch
ApplyOptionalPatch 0561-fix-using-algorithms-to-filter.patch
ApplyOptionalPatch 0562-feat-npu-driver-print-valt-and-rate.patch
ApplyOptionalPatch 0563-fix-fix-lpcpu-dump-failed-Changelogs-1.-fix-lpcpu-du.patch
ApplyOptionalPatch 0564-fix-modify-model-name.patch
ApplyOptionalPatch 0565-fix-modify-the-reference-temperature.patch
ApplyOptionalPatch 0566-feat-support-eic7700-fccsp-evb-a1.patch
ApplyOptionalPatch 0567-chore-Make-es_proc-as-common-interfaces.patch
ApplyOptionalPatch 0568-fix-lspci-issue-after-reboot.patch
ApplyOptionalPatch 0569-feat-revert-lpcpu-modifications.patch
ApplyOptionalPatch 0570-feat-Display-LOGO-during-kernel-bootup.patch
ApplyOptionalPatch 0571-chore-fix-es_porc-builtin-issue.patch
ApplyOptionalPatch 0572-feat-2d-add-hardware-load-statistics-with-proc-show.patch
ApplyOptionalPatch 0573-fix-fix-EVB-MIPI-spupport-MP-test.patch
ApplyOptionalPatch 0574-fix-usb-dwc3-eswin-Fix-section-mismatch.patch
ApplyOptionalPatch 0575-fix-drivers-sound-eswin-Add-mutex-in-module_exit.patch
ApplyOptionalPatch 0576-fix-smmu-lockdep_assert_held-error-in-groups.patch
ApplyOptionalPatch 0577-feature-Fix-kexec-job-depend-on-proc-iomem-reserved.patch
ApplyOptionalPatch 0578-feature-Add-CONFIG_KEXEC-and-SYSRQ-config.patch
ApplyOptionalPatch 0579-feat-Add-statistics-of-NPU-frame-rate.patch
ApplyOptionalPatch 0580-fix-modify-temperature-to-65-75-105.patch
ApplyOptionalPatch 0581-fix-pvt0-label-info-inaccurate.patch
ApplyOptionalPatch 0582-feature-Remove-CONFIG_DEBUG_INFO.patch
ApplyOptionalPatch 0583-feat-Merge-branch-feature-vi-into-dev.patch
ApplyOptionalPatch 0584-fix-remove-DRIVER_MODSET-flag-from-img.patch
ApplyOptionalPatch 0585-fix-enable-npu-and-dsp-in-dts-Changelogs.patch
ApplyOptionalPatch 0586-fix-dmabuf-dma_resv-lock-was-not-held.patch
ApplyOptionalPatch 0587-fix-fix-vi-0630.patch
ApplyOptionalPatch 0588-feature-Add-kdb-config-and-ftrace-config.patch
ApplyOptionalPatch 0589-perf-Optimize-CPU-voltage-and-cpufreq-control.patch
ApplyOptionalPatch 0590-feat-add-aicard-feature-Changelogs.patch
ApplyOptionalPatch 0591-fix-vpu-pcie-streamid-problem.patch
ApplyOptionalPatch 0592-fix-eic7700-cpu-voltage-and-cpufreq-control-failed.patch
ApplyOptionalPatch 0593-feat-Update-vpu7702-pcie-a2.dts.patch
ApplyOptionalPatch 0594-fix-2d-hardware-usage-timer-func-release-mutex-faile.patch
ApplyOptionalPatch 0595-fix-fix-nid-check-bug-in-flush_all.patch
ApplyOptionalPatch 0596-chore-move-es_proc.h-to-commom-dir.patch
ApplyOptionalPatch 0597-fix-check-d2d-recovery-status.patch
ApplyOptionalPatch 0598-fix-fix-smmu-print-level.patch
ApplyOptionalPatch 0599-fix-disable-wifi-by-default.patch
ApplyOptionalPatch 0600-feature-Support-trigger-kdump-when-rcu-stall.patch
ApplyOptionalPatch 0601-fix-clear-log-for-ap6256.patch
ApplyOptionalPatch 0602-fix-vdec-fix-dead-lock-issue-for-vdec-driver.patch
ApplyOptionalPatch 0603-fix-Add-multi-batch-frame-rate-statistics.patch
ApplyOptionalPatch 0604-feat-Enable-npu-power-node.patch
ApplyOptionalPatch 0605-fix-fix-no-dewarp-devnode-on-7702.patch
ApplyOptionalPatch 0606-fix-cpufreq-switch-failed.patch
ApplyOptionalPatch 0607-feat-Support-ESWIN-s-TRNG.patch
ApplyOptionalPatch 0608-feat-support-fccsp-evb-mipi-csi.patch
ApplyOptionalPatch 0609-fix-fix-some-vi-warning-in-0630.patch
ApplyOptionalPatch 0610-feat-support-IPA-in-VPU.patch
ApplyOptionalPatch 0611-feat-support-eswin-s-hwrng.patch
ApplyOptionalPatch 0612-feat-support-fccsp-evb-mipi-csi.patch
ApplyOptionalPatch 0613-fix-clear-log-for-wifi-stop.patch
ApplyOptionalPatch 0614-feature-Add-reset-trigger-kdump-driver.patch
ApplyOptionalPatch 0615-feature-Sync-config-from-eic7700_defconfig.patch
ApplyOptionalPatch 0616-feature-Enable-pstore-feature-on-all-eic7700-eic7702.patch
ApplyOptionalPatch 0617-fix-fix-MIPI-DSI-reboot-panic.patch
ApplyOptionalPatch 0618-fix-add-dmabuf_helper-params-check.patch
ApplyOptionalPatch 0619-fix-Dual-die-rng-register.patch
ApplyOptionalPatch 0620-perf-dsiable-d2d-driver.patch
ApplyOptionalPatch 0621-feat-Refactor-PACMSG.patch
ApplyOptionalPatch 0622-fix-venc-venc-run-in-D1-cause-system-hang.patch
ApplyOptionalPatch 0623-fix-fusb303b-mutex-lock-used-before-initialization.patch
ApplyOptionalPatch 0624-fix-2d-kernel-stack-on-d2d-cherry-pick-4559ee5-from-.patch
ApplyOptionalPatch 0625-fix-2d-suspend-failed-cherry-pick-0284684-from-pm.patch
ApplyOptionalPatch 0626-fix-2d-power-off-delay-cherry-pick-c81694e-from-pm.patch
ApplyOptionalPatch 0627-fix-2d-process-stuck-cherry-pick-164de56-from-pm.patch
ApplyOptionalPatch 0628-feat-implement-cpu-read-data-from-lpcpu.patch
ApplyOptionalPatch 0629-fix-enable-pvt0-in-7702-boards-by-default.patch
ApplyOptionalPatch 0630-fix-d2d-support-thermal.patch
ApplyOptionalPatch 0631-fix-disabled-isp-for-feature-not-ready.patch
ApplyOptionalPatch 0632-fix-disabled-isp-for-feature-not-ready.patch
ApplyOptionalPatch 0633-feat-new-board-u2-evb.patch
ApplyOptionalPatch 0634-fix-fix-no-dewarp-dev-node.patch
ApplyOptionalPatch 0635-fix-2d-close-power-mangemnet.patch
ApplyOptionalPatch 0636-fix-Enable-sdio1-by-default-for-eic7700-sbc-a1-board.patch
ApplyOptionalPatch 0637-dts-sync-ramoops-for-megrez-nx-star64pro.patch
ApplyOptionalPatch 0638-config-sync-eic7700-config.patch
ApplyOptionalPatch 0639-UPSTREAM-selftests-riscv-Generalize-mm-selftests.patch
ApplyOptionalPatch 0640-UPSTREAM-docs-riscv-Define-behavior-of-mmap.patch
ApplyOptionalPatch 0641-UPSTREAM-riscv-selftests-Remove-mmap-hint-address-ch.patch
ApplyOptionalPatch 0642-UPSTREAM-Revert-RISC-V-mm-Document-mmap-changes.patch
ApplyOptionalPatch 0643-header-workarounds.patch
ApplyOptionalPatch 0644-stop-triggering-vmlinux-rebuild.patch
ApplyOptionalPatch 0645-Add-missing-newline.patch
ApplyOptionalPatch 0646-uninvert-the-fan.patch
ApplyOptionalPatch 0647-Reduce-crit-threshold-temp-to-85000.patch
ApplyOptionalPatch 0648-eswin-dsp-fixes.patch
ApplyOptionalPatch 0649-remove-mmz-vb-reserved-memory-ranges.patch
ApplyOptionalPatch 0650-Add-NPU-enabled-variants-of-dtbs.patch
ApplyOptionalPatch 0651-Bring-back-1.8GHz-to-STARPro64.patch
ApplyOptionalPatch 0652-remove-makefile-reference-for-non-existent-directory.patch





%endif

ApplyOptionalPatch linux-kernel-test.patch

# END OF PATCH APPLICATIONS

# Any further pre-build tree manipulations happen here.

chmod +x scripts/checkpatch.pl
mv COPYING COPYING-%{specrpmversion}-%{release}

# on linux-next prevent scripts/setlocalversion from mucking with our version numbers
rm -f localversion-next

# Mangle /usr/bin/python shebangs to /usr/bin/python3
# Mangle all Python shebangs to be Python 3 explicitly
# -p preserves timestamps
# -n prevents creating ~backup files
# -i specifies the interpreter for the shebang
# This fixes errors such as
# *** ERROR: ambiguous python shebang in /usr/bin/kvm_stat: #!/usr/bin/python. Change it to python3 (or python2) explicitly.
# We patch all sources below for which we got a report/error.
echo "Fixing Python shebangs..."
%py3_shebang_fix \
	tools/kvm/kvm_stat/kvm_stat \
	scripts/show_delta \
	scripts/diffconfig \
	scripts/bloat-o-meter \
	scripts/jobserver-exec \
	tools \
	Documentation \
	scripts/clang-tools 2> /dev/null

# only deal with configs if we are going to build for the arch
%ifnarch %nobuildarches

if [ -L configs ]; then
	rm -f configs
fi
mkdir configs
cd configs

# Drop some necessary files from the source dir into the buildroot
cp $RPM_SOURCE_DIR/%{name}-*.config .
cp %{SOURCE80} .
# merge.py
cp %{SOURCE3000} .
# kernel-local - rename and copy for partial snippet config process
cp %{SOURCE3001} partial-kernel-local-snip.config
cp %{SOURCE3001} partial-kernel-local-debug-snip.config
FLAVOR=%{primary_target} SPECPACKAGE_NAME=%{name} SPECVERSION=%{specversion} SPECRPMVERSION=%{specrpmversion} ./generate_all_configs.sh %{debugbuildsenabled}

# Collect custom defined config options
PARTIAL_CONFIGS=""
%if %{with_gcov}
PARTIAL_CONFIGS="$PARTIAL_CONFIGS %{SOURCE70} %{SOURCE71}"
%endif
%if %{with toolchain_clang}
PARTIAL_CONFIGS="$PARTIAL_CONFIGS %{SOURCE72} %{SOURCE73}"
%endif
%if %{with clang_lto}
PARTIAL_CONFIGS="$PARTIAL_CONFIGS %{SOURCE74} %{SOURCE75} %{SOURCE76} %{SOURCE77}"
%endif
PARTIAL_CONFIGS="$PARTIAL_CONFIGS partial-kernel-local-snip.config partial-kernel-local-debug-snip.config"

GetArch()
{
  case "$1" in
  *aarch64*) echo "aarch64" ;;
  *ppc64le*) echo "ppc64le" ;;
  *s390x*) echo "s390x" ;;
  *riscv64*) echo "riscv64" ;;
  *x86_64*) echo "x86_64" ;;
  # no arch, apply everywhere
  *) echo "" ;;
  esac
}

# Merge in any user-provided local config option changes
%ifnarch %nobuildarches
for i in %{all_configs}
do
  kern_arch="$(GetArch $i)"
  kern_debug="$(echo $i | grep -q debug && echo "debug" || echo "")"

  for j in $PARTIAL_CONFIGS
  do
    part_arch="$(GetArch $j)"
    part_debug="$(echo $j | grep -q debug && echo "debug" || echo "")"

    # empty arch means apply to all arches
    if [ "$part_arch" == "" -o "$part_arch" == "$kern_arch" ] && [ "$part_debug" == "$kern_debug" ]
    then
      mv $i $i.tmp
      ./merge.py $j $i.tmp > $i
    fi
  done
  rm -f $i.tmp
done
%endif

# Add DUP and kpatch certificates to system trusted keys for RHEL
%if 0%{?rhel}
%if %{signkernel}%{signmodules}
openssl x509 -inform der -in %{SOURCE100} -out rheldup3.pem
openssl x509 -inform der -in %{SOURCE101} -out rhelkpatch1.pem
cat rheldup3.pem rhelkpatch1.pem > ../certs/rhel.pem
%ifarch s390x ppc64le
openssl x509 -inform der -in %{secureboot_ca_0} -out secureboot.pem
cat secureboot.pem >> ../certs/rhel.pem
%endif
for i in *.config; do
  sed -i 's@CONFIG_SYSTEM_TRUSTED_KEYS=""@CONFIG_SYSTEM_TRUSTED_KEYS="certs/rhel.pem"@' $i
done
%endif
%endif

# Adjust FIPS module name for RHEL
%if 0%{?rhel}
for i in *.config; do
  sed -i 's/CONFIG_CRYPTO_FIPS_NAME=.*/CONFIG_CRYPTO_FIPS_NAME="Red Hat Enterprise Linux %{rhel} - Kernel Cryptographic API"/' $i
done
%endif

cp %{SOURCE81} .
OPTS=""
%if %{with_configchecks}
	OPTS="$OPTS -w -n -c"
%endif
%if %{with clang_lto}
for opt in %{clang_make_opts}; do
  OPTS="$OPTS -m $opt"
done
%endif
RHJOBS=$RPM_BUILD_NCPUS SPECPACKAGE_NAME=%{name} ./process_configs.sh $OPTS %{specrpmversion}

cp %{SOURCE82} .
RPM_SOURCE_DIR=$RPM_SOURCE_DIR ./update_scripts.sh %{primary_target}

# We may want to override files from the primary target in case of building
# against a flavour of it (eg. centos not rhel), thus override it here if
# necessary
if [ "%{primary_target}" == "rhel" ]; then
%if 0%{?centos}
  echo "Updating scripts/sources to centos version"
  RPM_SOURCE_DIR=$RPM_SOURCE_DIR ./update_scripts.sh centos
%else
  echo "Not updating scripts/sources to centos version"
%endif
fi

# end of kernel config
%endif

cd ..
# # End of Configs stuff

# get rid of unwanted files resulting from patch fuzz
find . \( -name "*.orig" -o -name "*~" \) -delete >/dev/null

# remove unnecessary SCM files
find . -name .gitignore -delete >/dev/null

cd ..

###
### build
###
%build

rm -rf %{buildroot_unstripped} || true
mkdir -p %{buildroot_unstripped}

%if %{with_sparse}
%define sparse_mflags	C=1
%endif

cp_vmlinux()
{
  eu-strip --remove-comment -o "$2" "$1"
}

# Note we need to disable these flags for cross builds because the flags
# from redhat-rpm-config assume that host == target so target arch
# flags cause issues with the host compiler.
%if !%{with_cross}
%define build_hostcflags  %{?build_cflags}
%define build_hostldflags %{?build_ldflags}
%endif

%define make %{__make} %{?cross_opts} %{?make_opts} HOSTCFLAGS="%{?build_hostcflags}" HOSTLDFLAGS="%{?build_hostldflags}"

InitBuildVars() {
    # Initialize the kernel .config file and create some variables that are
    # needed for the actual build process.

    Variant=$1

    # Pick the right kernel config file
    Config=%{name}-%{specrpmversion}-%{_target_cpu}${Variant:+-${Variant}}.config
    DevelDir=/usr/src/kernels/%{KVERREL}${Variant:++${Variant}}

    KernelVer=%{specversion}-%{release}.%{_target_cpu}${Variant:++${Variant}}

    # make sure EXTRAVERSION says what we want it to say
    # Trim the release if this is a CI build, since KERNELVERSION is limited to 64 characters
    ShortRel=$(perl -e "print \"%{release}\" =~ s/\.pr\.[0-9A-Fa-f]{32}//r")
    perl -p -i -e "s/^EXTRAVERSION.*/EXTRAVERSION = -${ShortRel}.%{_target_cpu}${Variant:++${Variant}}/" Makefile

    # if pre-rc1 devel kernel, must fix up PATCHLEVEL for our versioning scheme
    # if we are post rc1 this should match anyway so this won't matter
    perl -p -i -e 's/^PATCHLEVEL.*/PATCHLEVEL = %{patchlevel}/' Makefile

    %{make} %{?_smp_mflags} mrproper
    cp configs/$Config .config

    %if %{signkernel}%{signmodules}
    cp configs/x509.genkey certs/.
    %endif

    Arch=`head -1 .config | cut -b 3-`
    echo USING ARCH=$Arch

    KCFLAGS="%{?kcflags}"

    # add kpatch flags for base kernel
    if [ "$Variant" == "" ]; then
        KCFLAGS="$KCFLAGS %{?kpatch_kcflags}"
    fi
}

BuildKernel() {
    MakeTarget=$1
    KernelImage=$2
    DoVDSO=$3
    Variant=$4
    InstallName=${5:-vmlinuz}

    DoModules=1
    if [ "$Variant" = "zfcpdump" ]; then
	    DoModules=0
    fi

    # When the bootable image is just the ELF kernel, strip it.
    # We already copy the unstripped file into the debuginfo package.
    if [ "$KernelImage" = vmlinux ]; then
      CopyKernel=cp_vmlinux
    else
      CopyKernel=cp
    fi

%if %{with_gcov}
    # Make build directory unique for each variant, so that gcno symlinks
    # are also unique for each variant.
    if [ -n "$Variant" ]; then
        ln -s $(pwd) ../linux-%{KVERREL}-${Variant}
    fi
    echo "GCOV - continuing build in: $(pwd)"
    pushd ../linux-%{KVERREL}${Variant:+-${Variant}}
    pwd > ../kernel${Variant:+-${Variant}}-gcov.list
%endif

    InitBuildVars $Variant

    echo BUILDING A KERNEL FOR ${Variant} %{_target_cpu}...

    %{make} ARCH=$Arch olddefconfig >/dev/null

    # This ensures build-ids are unique to allow parallel debuginfo
    perl -p -i -e "s/^CONFIG_BUILD_SALT.*/CONFIG_BUILD_SALT=\"%{KVERREL}\"/" .config
    %{make} ARCH=$Arch KCFLAGS="$KCFLAGS" WITH_GCOV="%{?with_gcov}" %{?_smp_mflags} $MakeTarget %{?sparse_mflags} %{?kernel_mflags}
    if [ $DoModules -eq 1 ]; then
	%{make} ARCH=$Arch KCFLAGS="$KCFLAGS" WITH_GCOV="%{?with_gcov}" %{?_smp_mflags} modules %{?sparse_mflags} || exit 1
    fi

    mkdir -p $RPM_BUILD_ROOT/%{image_install_path}
    mkdir -p $RPM_BUILD_ROOT/lib/modules/$KernelVer
    mkdir -p $RPM_BUILD_ROOT/lib/modules/$KernelVer/systemtap
%if %{with_debuginfo}
    mkdir -p $RPM_BUILD_ROOT%{debuginfodir}/%{image_install_path}
%endif

%ifarch aarch64 riscv64
    %{make} ARCH=$Arch dtbs INSTALL_DTBS_PATH=$RPM_BUILD_ROOT/%{image_install_path}/dtb-$KernelVer
    %{make} ARCH=$Arch dtbs_install INSTALL_DTBS_PATH=$RPM_BUILD_ROOT/%{image_install_path}/dtb-$KernelVer
    cp -r $RPM_BUILD_ROOT/%{image_install_path}/dtb-$KernelVer $RPM_BUILD_ROOT/lib/modules/$KernelVer/dtb
    find arch/$Arch/boot/dts -name '*.dtb' -type f -delete
%endif

    # Remove large intermediate files we no longer need to save space
    # (-f required for zfcpdump builds that do not enable BTF)
    rm -f vmlinux.o .tmp_vmlinux.btf

    # Start installing the results
    install -m 644 .config $RPM_BUILD_ROOT/boot/config-$KernelVer
    install -m 644 .config $RPM_BUILD_ROOT/lib/modules/$KernelVer/config
    install -m 644 System.map $RPM_BUILD_ROOT/boot/System.map-$KernelVer
    install -m 644 System.map $RPM_BUILD_ROOT/lib/modules/$KernelVer/System.map

    # We estimate the size of the initramfs because rpm needs to take this size
    # into consideration when performing disk space calculations. (See bz #530778)
    dd if=/dev/zero of=$RPM_BUILD_ROOT/boot/initramfs-$KernelVer.img bs=1M count=20

    if [ -f arch/$Arch/boot/zImage.stub ]; then
      cp arch/$Arch/boot/zImage.stub $RPM_BUILD_ROOT/%{image_install_path}/zImage.stub-$KernelVer || :
      cp arch/$Arch/boot/zImage.stub $RPM_BUILD_ROOT/lib/modules/$KernelVer/zImage.stub-$KernelVer || :
    fi

    %if %{signkernel}
    if [ "$KernelImage" = vmlinux ]; then
        # We can't strip and sign $KernelImage in place, because
        # we need to preserve original vmlinux for debuginfo.
        # Use a copy for signing.
        $CopyKernel $KernelImage $KernelImage.tosign
        KernelImage=$KernelImage.tosign
        CopyKernel=cp
    fi

    SignImage=$KernelImage

    %ifarch x86_64 aarch64
    %pesign -s -i $SignImage -o vmlinuz.tmp -a %{secureboot_ca_0} -c %{secureboot_key_0} -n %{pesign_name_0}
    %pesign -s -i vmlinuz.tmp -o vmlinuz.signed -a %{secureboot_ca_1} -c %{secureboot_key_1} -n %{pesign_name_1}
    rm vmlinuz.tmp
    %endif
    %ifarch s390x ppc64le
    if [ -x /usr/bin/rpm-sign ]; then
	rpm-sign --key "%{pesign_name_0}" --lkmsign $SignImage --output vmlinuz.signed
    elif [ $DoModules -eq 1 ]; then
	chmod +x scripts/sign-file
	./scripts/sign-file -p sha256 certs/signing_key.pem certs/signing_key.x509 $SignImage vmlinuz.signed
    else
	mv $SignImage vmlinuz.signed
    fi
    %endif

    if [ ! -s vmlinuz.signed ]; then
        echo "pesigning failed"
        exit 1
    fi
    mv vmlinuz.signed $SignImage
    # signkernel
    %endif

    $CopyKernel $KernelImage \
                $RPM_BUILD_ROOT/%{image_install_path}/$InstallName-$KernelVer
    chmod 755 $RPM_BUILD_ROOT/%{image_install_path}/$InstallName-$KernelVer
    cp $RPM_BUILD_ROOT/%{image_install_path}/$InstallName-$KernelVer $RPM_BUILD_ROOT/lib/modules/$KernelVer/$InstallName

    # hmac sign the kernel for FIPS
    echo "Creating hmac file: $RPM_BUILD_ROOT/%{image_install_path}/.vmlinuz-$KernelVer.hmac"
    ls -l $RPM_BUILD_ROOT/%{image_install_path}/$InstallName-$KernelVer
    (cd $RPM_BUILD_ROOT/%{image_install_path} && sha512hmac $InstallName-$KernelVer) > $RPM_BUILD_ROOT/%{image_install_path}/.vmlinuz-$KernelVer.hmac;
    cp $RPM_BUILD_ROOT/%{image_install_path}/.vmlinuz-$KernelVer.hmac $RPM_BUILD_ROOT/lib/modules/$KernelVer/.vmlinuz.hmac

    if [ $DoModules -eq 1 ]; then
	# Override $(mod-fw) because we don't want it to install any firmware
	# we'll get it from the linux-firmware package and we don't want conflicts
	%{make} %{?_smp_mflags} ARCH=$Arch INSTALL_MOD_PATH=$RPM_BUILD_ROOT %{?_smp_mflags} modules_install KERNELRELEASE=$KernelVer mod-fw=
    fi

%if %{with_gcov}
    # install gcov-needed files to $BUILDROOT/$BUILD/...:
    #   gcov_info->filename is absolute path
    #   gcno references to sources can use absolute paths (e.g. in out-of-tree builds)
    #   sysfs symlink targets (set up at compile time) use absolute paths to BUILD dir
    find . \( -name '*.gcno' -o -name '*.[chS]' \) -exec install -D '{}' "$RPM_BUILD_ROOT/$(pwd)/{}" \;
%endif

    # add an a noop %%defattr statement 'cause rpm doesn't like empty file list files
    echo '%%defattr(-,-,-)' > ../kernel${Variant:+-${Variant}}-ldsoconf.list
    if [ $DoVDSO -ne 0 ]; then
        %{make} ARCH=$Arch INSTALL_MOD_PATH=$RPM_BUILD_ROOT vdso_install KERNELRELEASE=$KernelVer
        if [ -s ldconfig-kernel.conf ]; then
             install -D -m 444 ldconfig-kernel.conf \
                $RPM_BUILD_ROOT/etc/ld.so.conf.d/kernel-$KernelVer.conf
	     echo /etc/ld.so.conf.d/kernel-$KernelVer.conf >> ../kernel${Variant:+-${Variant}}-ldsoconf.list
        fi

        rm -rf $RPM_BUILD_ROOT/lib/modules/$KernelVer/vdso/.build-id
    fi

    # And save the headers/makefiles etc for building modules against
    #
    # This all looks scary, but the end result is supposed to be:
    # * all arch relevant include/ files
    # * all Makefile/Kconfig files
    # * all script/ files

    rm -f $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    rm -f $RPM_BUILD_ROOT/lib/modules/$KernelVer/source
    mkdir -p $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    (cd $RPM_BUILD_ROOT/lib/modules/$KernelVer ; ln -s build source)
    # dirs for additional modules per module-init-tools, kbuild/modules.txt
    mkdir -p $RPM_BUILD_ROOT/lib/modules/$KernelVer/updates
    mkdir -p $RPM_BUILD_ROOT/lib/modules/$KernelVer/weak-updates
    # CONFIG_KERNEL_HEADER_TEST generates some extra files in the process of
    # testing so just delete
    find . -name *.h.s -delete
    # first copy everything
    cp --parents `find  -type f -name "Makefile*" -o -name "Kconfig*"` $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    if [ ! -e Module.symvers ]; then
        touch Module.symvers
    fi
    cp Module.symvers $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp System.map $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    if [ -s Module.markers ]; then
      cp Module.markers $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    fi

    # create the kABI metadata for use in packaging
    # NOTENOTE: the name symvers is used by the rpm backend
    # NOTENOTE: to discover and run the /usr/lib/rpm/fileattrs/kabi.attr
    # NOTENOTE: script which dynamically adds exported kernel symbol
    # NOTENOTE: checksums to the rpm metadata provides list.
    # NOTENOTE: if you change the symvers name, update the backend too
    echo "**** GENERATING kernel ABI metadata ****"
    %compression --stdout %compression_flags < Module.symvers > $RPM_BUILD_ROOT/boot/symvers-$KernelVer.%compext
    cp $RPM_BUILD_ROOT/boot/symvers-$KernelVer.%compext $RPM_BUILD_ROOT/lib/modules/$KernelVer/symvers.%compext

%if %{with_kabichk}
    echo "**** kABI checking is enabled in kernel SPEC file. ****"
    chmod 0755 $RPM_SOURCE_DIR/check-kabi
    if [ -e $RPM_SOURCE_DIR/Module.kabi_%{_target_cpu}$Variant ]; then
        cp $RPM_SOURCE_DIR/Module.kabi_%{_target_cpu}$Variant $RPM_BUILD_ROOT/Module.kabi
        $RPM_SOURCE_DIR/check-kabi -k $RPM_BUILD_ROOT/Module.kabi -s Module.symvers || exit 1
        # for now, don't keep it around.
        rm $RPM_BUILD_ROOT/Module.kabi
    else
        echo "**** NOTE: Cannot find reference Module.kabi file. ****"
    fi
%endif

%if %{with_kabidupchk}
    echo "**** kABI DUP checking is enabled in kernel SPEC file. ****"
    if [ -e $RPM_SOURCE_DIR/Module.kabi_dup_%{_target_cpu}$Variant ]; then
        cp $RPM_SOURCE_DIR/Module.kabi_dup_%{_target_cpu}$Variant $RPM_BUILD_ROOT/Module.kabi
        $RPM_SOURCE_DIR/check-kabi -k $RPM_BUILD_ROOT/Module.kabi -s Module.symvers || exit 1
        # for now, don't keep it around.
        rm $RPM_BUILD_ROOT/Module.kabi
    else
        echo "**** NOTE: Cannot find DUP reference Module.kabi file. ****"
    fi
%endif

%if %{with_kabidw_base}
    # Don't build kabi base for debug kernels
    if [ "$Variant" != "zfcpdump" -a "$Variant" != "debug" ]; then
        mkdir -p $RPM_BUILD_ROOT/kabi-dwarf
        tar -xvf %{SOURCE301} -C $RPM_BUILD_ROOT/kabi-dwarf

        mkdir -p $RPM_BUILD_ROOT/kabi-dwarf/stablelists
        tar -xvf %{SOURCE300} -C $RPM_BUILD_ROOT/kabi-dwarf/stablelists

        echo "**** GENERATING DWARF-based kABI baseline dataset ****"
        chmod 0755 $RPM_BUILD_ROOT/kabi-dwarf/run_kabi-dw.sh
        $RPM_BUILD_ROOT/kabi-dwarf/run_kabi-dw.sh generate \
            "$RPM_BUILD_ROOT/kabi-dwarf/stablelists/kabi-current/kabi_stablelist_%{_target_cpu}" \
            "$(pwd)" \
            "$RPM_BUILD_ROOT/kabidw-base/%{_target_cpu}${Variant:+.${Variant}}" || :

        rm -rf $RPM_BUILD_ROOT/kabi-dwarf
    fi
%endif

%if %{with_kabidwchk}
    if [ "$Variant" != "zfcpdump" ]; then
        mkdir -p $RPM_BUILD_ROOT/kabi-dwarf
        tar -xvf %{SOURCE301} -C $RPM_BUILD_ROOT/kabi-dwarf
        if [ -d "$RPM_BUILD_ROOT/kabi-dwarf/base/%{_target_cpu}${Variant:+.${Variant}}" ]; then
            mkdir -p $RPM_BUILD_ROOT/kabi-dwarf/stablelists
            tar -xvf %{SOURCE300} -C $RPM_BUILD_ROOT/kabi-dwarf/stablelists

            echo "**** GENERATING DWARF-based kABI dataset ****"
            chmod 0755 $RPM_BUILD_ROOT/kabi-dwarf/run_kabi-dw.sh
            $RPM_BUILD_ROOT/kabi-dwarf/run_kabi-dw.sh generate \
                "$RPM_BUILD_ROOT/kabi-dwarf/stablelists/kabi-current/kabi_stablelist_%{_target_cpu}" \
                "$(pwd)" \
                "$RPM_BUILD_ROOT/kabi-dwarf/base/%{_target_cpu}${Variant:+.${Variant}}.tmp" || :

            echo "**** kABI DWARF-based comparison report ****"
            $RPM_BUILD_ROOT/kabi-dwarf/run_kabi-dw.sh compare \
                "$RPM_BUILD_ROOT/kabi-dwarf/base/%{_target_cpu}${Variant:+.${Variant}}" \
                "$RPM_BUILD_ROOT/kabi-dwarf/base/%{_target_cpu}${Variant:+.${Variant}}.tmp" || :
            echo "**** End of kABI DWARF-based comparison report ****"
        else
            echo "**** Baseline dataset for kABI DWARF-BASED comparison report not found ****"
        fi

        rm -rf $RPM_BUILD_ROOT/kabi-dwarf
    fi
%endif

    # then drop all but the needed Makefiles/Kconfig files
    rm -rf $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/scripts
    rm -rf $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/include
    cp .config $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a scripts $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    rm -rf $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/scripts/tracing
    rm -f $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/scripts/spdxcheck.py

%ifarch s390x
    # CONFIG_EXPOLINE_EXTERN=y produces arch/s390/lib/expoline/expoline.o
    # which is needed during external module build.
    if [ -f arch/s390/lib/expoline/expoline.o ]; then
      cp -a --parents arch/s390/lib/expoline/expoline.o $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    fi
%endif

    # Files for 'make scripts' to succeed with kernel-devel.
    mkdir -p $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/security/selinux/include
    cp -a --parents security/selinux/include/classmap.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents security/selinux/include/initial_sid_to_string.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    mkdir -p $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/tools/include/tools
    cp -a --parents tools/include/tools/be_byteshift.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/include/tools/le_byteshift.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build

    # Files for 'make prepare' to succeed with kernel-devel.
    cp -a --parents tools/include/linux/compiler* $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/include/linux/types.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/build/Build.include $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents tools/build/Build $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents tools/build/fixdep.c $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents tools/objtool/sync-check.sh $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/bpf/resolve_btfids/main.c $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/bpf/resolve_btfids/Build $RPM_BUILD_ROOT/lib/modules/$KernelVer/build

    cp --parents security/selinux/include/policycap_names.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents security/selinux/include/policycap.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build

    cp -a --parents tools/include/asm-generic $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/include/linux $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/include/uapi/asm $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/include/uapi/asm-generic $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/include/uapi/linux $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/include/vdso $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents tools/scripts/utilities.mak $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/lib/subcmd $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents tools/lib/*.c $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents tools/objtool/*.[ch] $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents tools/objtool/Build $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents tools/objtool/include/objtool/*.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/lib/bpf $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents tools/lib/bpf/Build $RPM_BUILD_ROOT/lib/modules/$KernelVer/build

    if [ -f tools/objtool/objtool ]; then
      cp -a tools/objtool/objtool $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/tools/objtool/ || :
    fi
    if [ -f tools/objtool/fixdep ]; then
      cp -a tools/objtool/fixdep $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/tools/objtool/ || :
    fi
    if [ -d arch/$Arch/scripts ]; then
      cp -a arch/$Arch/scripts $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/arch/%{_arch} || :
    fi
    if [ -f arch/$Arch/*lds ]; then
      cp -a arch/$Arch/*lds $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/arch/%{_arch}/ || :
    fi
    if [ -f arch/%{asmarch}/kernel/module.lds ]; then
      cp -a --parents arch/%{asmarch}/kernel/module.lds $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    fi
    find $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/scripts \( -iname "*.o" -o -iname "*.cmd" \) -exec rm -f {} +
%ifarch ppc64le
    cp -a --parents arch/powerpc/lib/crtsavres.[So] $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
%endif
    if [ -d arch/%{asmarch}/include ]; then
      cp -a --parents arch/%{asmarch}/include $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    fi
%ifarch aarch64
    # arch/arm64/include/asm/xen references arch/arm
    cp -a --parents arch/arm/include/asm/xen $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    # arch/arm64/include/asm/opcodes.h references arch/arm
    cp -a --parents arch/arm/include/asm/opcodes.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
%endif
    cp -a include $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/include
%ifarch i686 x86_64
    # files for 'make prepare' to succeed with kernel-devel
    cp -a --parents arch/x86/entry/syscalls/syscall_32.tbl $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/entry/syscalls/syscall_64.tbl $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/tools/relocs_32.c $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/tools/relocs_64.c $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/tools/relocs.c $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/tools/relocs_common.c $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/tools/relocs.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/purgatory/purgatory.c $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/purgatory/stack.S $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/purgatory/setup-x86_64.S $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/purgatory/entry64.S $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/boot/string.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/boot/string.c $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/boot/ctype.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/

    cp -a --parents scripts/syscalltbl.sh $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents scripts/syscallhdr.sh $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/

    cp -a --parents tools/arch/x86/include/asm $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/arch/x86/include/uapi/asm $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/objtool/arch/x86/lib $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/arch/x86/lib/ $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/arch/x86/tools/gen-insn-attr-x86.awk $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/objtool/arch/x86/ $RPM_BUILD_ROOT/lib/modules/$KernelVer/build

%endif
    # Clean up intermediate tools files
    find $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/tools \( -iname "*.o" -o -iname "*.cmd" \) -exec rm -f {} +

    # Make sure the Makefile, version.h, and auto.conf have a matching
    # timestamp so that external modules can be built
    touch -r $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/Makefile \
        $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/include/generated/uapi/linux/version.h \
        $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/include/config/auto.conf

%if %{with_debuginfo}
    eu-readelf -n vmlinux | grep "Build ID" | awk '{print $NF}' > vmlinux.id
    cp vmlinux.id $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/vmlinux.id

    #
    # save the vmlinux file for kernel debugging into the kernel-debuginfo rpm
    # (use mv + symlink instead of cp to reduce disk space requirements)
    #
    mkdir -p $RPM_BUILD_ROOT%{debuginfodir}/lib/modules/$KernelVer
    mv vmlinux $RPM_BUILD_ROOT%{debuginfodir}/lib/modules/$KernelVer
    ln -s $RPM_BUILD_ROOT%{debuginfodir}/lib/modules/$KernelVer/vmlinux vmlinux
    if [ -n "%{?vmlinux_decompressor}" ]; then
	    eu-readelf -n  %{vmlinux_decompressor} | grep "Build ID" | awk '{print $NF}' > vmlinux.decompressor.id
	    # Without build-id the build will fail. But for s390 the build-id
	    # wasn't added before 5.11. In case it is missing prefer not
	    # packaging the debuginfo over a build failure.
	    if [ -s vmlinux.decompressor.id ]; then
		    cp vmlinux.decompressor.id $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/vmlinux.decompressor.id
		    cp %{vmlinux_decompressor} $RPM_BUILD_ROOT%{debuginfodir}/lib/modules/$KernelVer/vmlinux.decompressor
	    fi
    fi
%endif

    find $RPM_BUILD_ROOT/lib/modules/$KernelVer -name "*.ko" -type f >modnames

    # mark modules executable so that strip-to-file can strip them
    xargs --no-run-if-empty chmod u+x < modnames

    # Generate a list of modules for block and networking.

    grep -F /drivers/ modnames | xargs --no-run-if-empty nm -upA |
    sed -n 's,^.*/\([^/]*\.ko\):  *U \(.*\)$,\1 \2,p' > drivers.undef

    collect_modules_list()
    {
      sed -r -n -e "s/^([^ ]+) \\.?($2)\$/\\1/p" drivers.undef |
        LC_ALL=C sort -u > $RPM_BUILD_ROOT/lib/modules/$KernelVer/modules.$1
      if [ ! -z "$3" ]; then
        sed -r -e "/^($3)\$/d" -i $RPM_BUILD_ROOT/lib/modules/$KernelVer/modules.$1
      fi
    }

    collect_modules_list networking \
      'register_netdev|ieee80211_register_hw|usbnet_probe|phy_driver_register|rt(l_|2x00)(pci|usb)_probe|register_netdevice'
    collect_modules_list block \
      'ata_scsi_ioctl|scsi_add_host|scsi_add_host_with_dma|blk_alloc_queue|blk_init_queue|register_mtd_blktrans|scsi_esp_register|scsi_register_device_handler|blk_queue_physical_block_size' 'pktcdvd.ko|dm-mod.ko'
    collect_modules_list drm \
      'drm_open|drm_init'
    collect_modules_list modesetting \
      'drm_crtc_init'

    # detect missing or incorrect license tags
    ( find $RPM_BUILD_ROOT/lib/modules/$KernelVer -name '*.ko' | xargs /sbin/modinfo -l | \
        grep -E -v 'GPL( v2)?$|Dual BSD/GPL$|Dual MPL/GPL$|GPL and additional rights$' ) && exit 1

    remove_depmod_files()
    {
        # remove files that will be auto generated by depmod at rpm -i time
        pushd $RPM_BUILD_ROOT/lib/modules/$KernelVer/
            # in case below list needs to be extended, remember to add a
            # matching ghost entry in the files section as well
            rm -f modules.{alias,alias.bin,builtin.alias.bin,builtin.bin} \
                  modules.{dep,dep.bin,devname,softdep,symbols,symbols.bin,weakdep}
        popd
    }

    remove_depmod_files

    # Identify modules in the kernel-modules-extras package
    %{SOURCE20} $RPM_BUILD_ROOT lib/modules/$KernelVer $(realpath configs/mod-extra.list)
    # Identify modules in the kernel-modules-internal package
    %{SOURCE20} $RPM_BUILD_ROOT lib/modules/$KernelVer %{SOURCE84} internal
%if 0%{!?fedora:1}
    # Identify modules in the kernel-modules-partner package
    %{SOURCE20} $RPM_BUILD_ROOT lib/modules/$KernelVer %{SOURCE85} partner
%endif
    if [[ "$Variant" == "rt" || "$Variant" == "rt-debug" ]]; then
    # Identify modules in the kernel-rt-kvm package
        %{SOURCE20} $RPM_BUILD_ROOT lib/modules/$KernelVer %{SOURCE400} kvm
    fi

    #
    # Generate the kernel-core and kernel-modules files lists
    #

    # Copy the System.map file for depmod to use, and create a backup of the
    # full module tree so we can restore it after we're done filtering
    cp System.map $RPM_BUILD_ROOT/.
    cp configs/filter-*.sh $RPM_BUILD_ROOT/.
    pushd $RPM_BUILD_ROOT
    mkdir restore
    cp -r lib/modules/$KernelVer/* restore/.

    # don't include anything going into kernel-modules-extra in the file lists
    xargs rm -rf < mod-extra.list
    # don't include anything going into kernel-modules-internal in the file lists
    xargs rm -rf < mod-internal.list
%if 0%{!?fedora:1}
    # don't include anything going into kernel-modules-partner in the file lists
    xargs rm -rf < mod-partner.list
%endif
    if [[ "$Variant" == "rt" || "$Variant" == "rt-debug" ]]; then
    	# don't include anything going into kernel-rt-kvm in the file lists
	xargs rm -rf < mod-kvm.list
    fi

    if [ $DoModules -eq 1 ]; then
	# Find all the module files and filter them out into the core and
	# modules lists.  This actually removes anything going into -modules
	# from the dir.
	find lib/modules/$KernelVer/kernel -name *.ko | sort -n > modules.list
	./filter-modules.sh modules.list %{_target_cpu}
	rm filter-*.sh

	# Run depmod on the resulting module tree and make sure it isn't broken
	depmod -b . -aeF ./System.map $KernelVer &> depmod.out
	if [ -s depmod.out ]; then
	    echo "Depmod failure"
	    cat depmod.out
	    exit 1
	else
	    rm depmod.out
	fi
    else
	# Ensure important files/directories exist to let the packaging succeed
	echo '%%defattr(-,-,-)' > modules.list
	echo '%%defattr(-,-,-)' > k-d.list
	mkdir -p lib/modules/$KernelVer/kernel
	# Add files usually created by make modules, needed to prevent errors
	# thrown by depmod during package installation
	touch lib/modules/$KernelVer/modules.order
	touch lib/modules/$KernelVer/modules.builtin
    fi

    if [[ "$Variant" == "rt" || "$Variant" == "rt-debug" ]]; then
        echo "Skipping efiuki build"
    else
%if %{with_efiuki}
	popd

	KernelUnifiedImageDir="$RPM_BUILD_ROOT/lib/modules/$KernelVer"
    	KernelUnifiedImage="$KernelUnifiedImageDir/$InstallName-virt.efi"

    	mkdir -p $KernelUnifiedImageDir

    	dracut --conf=%{SOURCE86} \
           --confdir=$(mktemp -d) \
           --verbose \
           --kver "$KernelVer" \
           --kmoddir "$RPM_BUILD_ROOT/lib/modules/$KernelVer/" \
           --logfile=$(mktemp) \
           --uefi \
           --kernel-image $(realpath $KernelImage) \
           --kernel-cmdline 'console=tty0 console=ttyS0' \
	   $KernelUnifiedImage

%if %{signkernel}

	%pesign -s -i $KernelUnifiedImage -o $KernelUnifiedImage.tmp -a %{secureboot_ca_0} -c %{secureboot_key_0} -n %{pesign_name_0}
    	%pesign -s -i $KernelUnifiedImage.tmp -o $KernelUnifiedImage.signed -a %{secureboot_ca_1} -c %{secureboot_key_1} -n %{pesign_name_1}
    	rm -f $KernelUnifiedImage.tmp

    	if [ ! -s $KernelUnifiedImage.signed ]; then
      	   echo "pesigning failed"
      	   exit 1
    	fi
    	mv $KernelUnifiedImage.signed $KernelUnifiedImage

# signkernel
%endif

	pushd $RPM_BUILD_ROOT

# with_efiuki
%endif
	:  # in case of empty block
    fi # "$Variant" == "rt" || "$Variant" == "rt-debug"

    remove_depmod_files

    # Go back and find all of the various directories in the tree.  We use this
    # for the dir lists in kernel-core
    find lib/modules/$KernelVer/kernel -mindepth 1 -type d | sort -n > module-dirs.list

    # Cleanup
    rm System.map
    # Just "cp -r" can be very slow: here, it rewrites _existing files_
    # with open(O_TRUNC). Many filesystems synchronously wait for metadata
    # update for such file rewrites (seen in strace as final close syscall
    # taking a long time). On a rotational disk, cp was observed to take
    # more than 5 minutes on ext4 and more than 15 minutes (!) on xfs.
    # With --remove-destination, we avoid this, and copying
    # (with enough RAM to cache it) takes 5 seconds:
    cp -r --remove-destination restore/* lib/modules/$KernelVer/.
    rm -rf restore
    popd

    # Make sure the files lists start with absolute paths or rpmbuild fails.
    # Also add in the dir entries
    sed -e 's/^lib*/\/lib/' %{?zipsed} $RPM_BUILD_ROOT/k-d.list > ../kernel${Variant:+-${Variant}}-modules.list
    sed -e 's/^lib*/%dir \/lib/' %{?zipsed} $RPM_BUILD_ROOT/module-dirs.list > ../kernel${Variant:+-${Variant}}-modules-core.list
    sed -e 's/^lib*/\/lib/' %{?zipsed} $RPM_BUILD_ROOT/modules.list >> ../kernel${Variant:+-${Variant}}-modules-core.list
    sed -e 's/^lib*/\/lib/' %{?zipsed} $RPM_BUILD_ROOT/mod-extra.list >> ../kernel${Variant:+-${Variant}}-modules-extra.list
    if [[ "$Variant" == "rt" || "$Variant" == "rt-debug" ]]; then
    	sed -e 's/^lib*/\/lib/' %{?zipsed} $RPM_BUILD_ROOT/mod-kvm.list >> ../kernel${Variant:+-${Variant}}-kvm.list
    fi

    # Cleanup
    rm -f $RPM_BUILD_ROOT/k-d.list
    rm -f $RPM_BUILD_ROOT/modules.list
    rm -f $RPM_BUILD_ROOT/module-dirs.list
    rm -f $RPM_BUILD_ROOT/mod-extra.list
    rm -f $RPM_BUILD_ROOT/mod-internal.list
%if 0%{!?fedora:1}
    rm -f $RPM_BUILD_ROOT/mod-partner.list
%endif
    if [[ "$Variant" == "rt" || "$Variant" == "rt-debug" ]]; then
    	rm -f $RPM_BUILD_ROOT/mod-kvm.list
    fi

%if %{signmodules}
    if [ $DoModules -eq 1 ]; then
	# Save the signing keys so we can sign the modules in __modsign_install_post
	cp certs/signing_key.pem certs/signing_key.pem.sign${Variant:++${Variant}}
	cp certs/signing_key.x509 certs/signing_key.x509.sign${Variant:++${Variant}}
    fi
%endif

    # Move the devel headers out of the root file system
    mkdir -p $RPM_BUILD_ROOT/usr/src/kernels
    mv $RPM_BUILD_ROOT/lib/modules/$KernelVer/build $RPM_BUILD_ROOT/$DevelDir

    # This is going to create a broken link during the build, but we don't use
    # it after this point.  We need the link to actually point to something
    # when kernel-devel is installed, and a relative link doesn't work across
    # the F17 UsrMove feature.
    ln -sf $DevelDir $RPM_BUILD_ROOT/lib/modules/$KernelVer/build

    # Generate vmlinux.h and put it to kernel-devel path
    # zfcpdump build does not have btf anymore
    if [ "$Variant" != "zfcpdump" ]; then
        bpftool btf dump file vmlinux format c > $RPM_BUILD_ROOT/$DevelDir/vmlinux.h
    fi

    # prune junk from kernel-devel
    find $RPM_BUILD_ROOT/usr/src/kernels -name ".*.cmd" -delete
    # prune junk from kernel-debuginfo
    find $RPM_BUILD_ROOT/usr/src/kernels -name "*.mod.c" -delete

    # Red Hat UEFI Secure Boot CA cert, which can be used to authenticate the kernel
    mkdir -p $RPM_BUILD_ROOT%{_datadir}/doc/kernel-keys/$KernelVer
    %ifarch x86_64 aarch64
       install -m 0644 %{secureboot_ca_0} $RPM_BUILD_ROOT%{_datadir}/doc/kernel-keys/$KernelVer/kernel-signing-ca-20200609.cer
       install -m 0644 %{secureboot_ca_1} $RPM_BUILD_ROOT%{_datadir}/doc/kernel-keys/$KernelVer/kernel-signing-ca-20140212.cer
       ln -s kernel-signing-ca-20200609.cer $RPM_BUILD_ROOT%{_datadir}/doc/kernel-keys/$KernelVer/kernel-signing-ca.cer
    %else
       install -m 0644 %{secureboot_ca_0} $RPM_BUILD_ROOT%{_datadir}/doc/kernel-keys/$KernelVer/kernel-signing-ca.cer
    %endif
    %ifarch s390x ppc64le
    if [ $DoModules -eq 1 ]; then
	if [ -x /usr/bin/rpm-sign ]; then
	    install -m 0644 %{secureboot_key_0} $RPM_BUILD_ROOT%{_datadir}/doc/kernel-keys/$KernelVer/%{signing_key_filename}
	else
	    install -m 0644 certs/signing_key.x509.sign${Variant:++${Variant}} $RPM_BUILD_ROOT%{_datadir}/doc/kernel-keys/$KernelVer/kernel-signing-ca.cer
	    openssl x509 -in certs/signing_key.pem.sign${Variant:++${Variant}} -outform der -out $RPM_BUILD_ROOT%{_datadir}/doc/kernel-keys/$KernelVer/%{signing_key_filename}
	    chmod 0644 $RPM_BUILD_ROOT%{_datadir}/doc/kernel-keys/$KernelVer/%{signing_key_filename}
	fi
    fi
    %endif

%if %{with_ipaclones}
    MAXPROCS=$(echo %{?_smp_mflags} | sed -n 's/-j\s*\([0-9]\+\)/\1/p')
    if [ -z "$MAXPROCS" ]; then
        MAXPROCS=1
    fi
    if [ "$Variant" == "" ]; then
        mkdir -p $RPM_BUILD_ROOT/$DevelDir-ipaclones
        find . -name '*.ipa-clones' | xargs -i{} -r -n 1 -P $MAXPROCS install -m 644 -D "{}" "$RPM_BUILD_ROOT/$DevelDir-ipaclones/{}"
    fi
%endif

%if %{with_gcov}
    popd
%endif
}

###
# DO it...
###

# prepare directories
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/boot
mkdir -p $RPM_BUILD_ROOT%{_libexecdir}

cd linux-%{KVERREL}


%if %{with_debug}
%if %{with_realtime}
echo "building rt-debug"
BuildKernel %make_target %kernel_image %{_use_vdso} rt-debug
%endif

%if %{with_arm64_16k}
BuildKernel %make_target %kernel_image %{_use_vdso} 16k-debug
%endif

%if %{with_arm64_64k}
BuildKernel %make_target %kernel_image %{_use_vdso} 64k-debug
%endif

%if %{with_up}
echo "building main debug package"
BuildKernel %make_target %kernel_image %{_use_vdso} debug
%endif
%endif

%if %{with_zfcpdump}
BuildKernel %make_target %kernel_image %{_use_vdso} zfcpdump
%endif

%if %{with_arm64_16k_base}
BuildKernel %make_target %kernel_image %{_use_vdso} 16k
%endif

%if %{with_arm64_64k_base}
BuildKernel %make_target %kernel_image %{_use_vdso} 64k
%endif

%if %{with_realtime_base}
BuildKernel %make_target %kernel_image %{_use_vdso} rt
%endif

%if %{with_up_base}
BuildKernel %make_target %kernel_image %{_use_vdso}
%endif

%ifnarch noarch i686 %{nobuildarches}
%if !%{with_debug} && !%{with_zfcpdump} && !%{with_up} && !%{with_arm64_16k} && !%{with_arm64_64k} && !%{with_realtime}
# If only building the user space tools, then initialize the build environment
# and some variables so that the various userspace tools can be built.
InitBuildVars
%endif
%endif

%ifarch aarch64
%global perf_build_extra_opts CORESIGHT=1
%endif
%global perf_make \
  %{__make} %{?make_opts} EXTRA_CFLAGS="${RPM_OPT_FLAGS}" LDFLAGS="%{__global_ldflags} -Wl,-E" %{?cross_opts} -C tools/perf V=1 NO_PERF_READ_VDSO32=1 NO_PERF_READ_VDSOX32=1 WERROR=0 NO_LIBUNWIND=1 HAVE_CPLUS_DEMANGLE=1 NO_GTK2=1 NO_STRLCPY=1 NO_BIONIC=1 LIBBPF_DYNAMIC=1 LIBTRACEEVENT_DYNAMIC=1 %{?perf_build_extra_opts} prefix=%{_prefix} PYTHON=%{__python3}
%if %{with_perf}
# perf
# make sure check-headers.sh is executable
chmod +x tools/perf/check-headers.sh
%{perf_make} DESTDIR=$RPM_BUILD_ROOT all
%endif

%global tools_make \
  CFLAGS="${RPM_OPT_FLAGS}" LDFLAGS="%{__global_ldflags}" %{make} %{?make_opts}

%if %{with_tools}
%ifarch %{cpupowerarchs}
# cpupower
# make sure version-gen.sh is executable.
chmod +x tools/power/cpupower/utils/version-gen.sh
%{tools_make} %{?_smp_mflags} -C tools/power/cpupower CPUFREQ_BENCH=false DEBUG=false
%ifarch x86_64
    pushd tools/power/cpupower/debug/x86_64
    %{tools_make} %{?_smp_mflags} centrino-decode powernow-k8-decode
    popd
%endif
%ifarch x86_64
   pushd tools/power/x86/x86_energy_perf_policy/
   %{tools_make}
   popd
   pushd tools/power/x86/turbostat
   %{tools_make}
   popd
   pushd tools/power/x86/intel-speed-select
   %{tools_make}
   popd
   pushd tools/arch/x86/intel_sdsi
   %{tools_make} CFLAGS="${RPM_OPT_FLAGS}"
   popd
%endif
%endif
pushd tools/thermal/tmon/
%{tools_make}
popd
pushd tools/iio/
%{tools_make}
popd
pushd tools/gpio/
%{tools_make}
popd
# build VM tools
pushd tools/mm/
%{tools_make} slabinfo page_owner_sort
popd
pushd tools/verification/rv/
%{tools_make}
popd
pushd tools/tracing/rtla
%{tools_make}
popd
%endif

if [ -f $DevelDir/vmlinux.h ]; then
  RPM_VMLINUX_H=$DevelDir/vmlinux.h
fi

%if %{with_bpftool}
%global bpftool_make \
  %{__make} EXTRA_CFLAGS="${RPM_OPT_FLAGS}" EXTRA_LDFLAGS="%{__global_ldflags}" DESTDIR=$RPM_BUILD_ROOT %{?make_opts} VMLINUX_H="${RPM_VMLINUX_H}" V=1
pushd tools/bpf/bpftool
%{bpftool_make}
popd
%else
echo "bpftools disabled ... disabling selftests"
%endif

%if %{with_selftests}
# Unfortunately, samples/bpf/Makefile expects that the headers are installed
# in the source tree. We installed them previously to $RPM_BUILD_ROOT/usr
# but there's no way to tell the Makefile to take them from there.
%{make} %{?_smp_mflags} headers_install

# If we re building only tools without kernel, we need to generate config
# headers and prepare tree for modules building. The modules_prepare target
# will cover both.
if [ ! -f include/generated/autoconf.h ]; then
   %{make} %{?_smp_mflags} modules_prepare
fi

%{make} %{?_smp_mflags} ARCH=$Arch V=1 M=samples/bpf/ VMLINUX_H="${RPM_VMLINUX_H}" || true

# Prevent bpf selftests to build bpftool repeatedly:
export BPFTOOL=$(pwd)/tools/bpf/bpftool/bpftool

pushd tools/testing/selftests
# We need to install here because we need to call make with ARCH set which
# doesn't seem possible to do in the install section.
%if %{selftests_must_build}
  force_targets="FORCE_TARGETS=1"
%else
  force_targets=""
%endif

%{make} %{?_smp_mflags} ARCH=$Arch V=1 TARGETS="bpf mm livepatch net net/forwarding net/mptcp netfilter tc-testing memfd drivers/net/bonding" SKIP_TARGETS="" $force_targets INSTALL_PATH=%{buildroot}%{_libexecdir}/kselftests VMLINUX_H="${RPM_VMLINUX_H}" install

# 'make install' for bpf is broken and upstream refuses to fix it.
# Install the needed files manually.
for dir in bpf bpf/no_alu32 bpf/progs; do
	# In ARK, the rpm build continues even if some of the selftests
	# cannot be built. It's not always possible to build selftests,
	# as upstream sometimes dependens on too new llvm version or has
	# other issues. If something did not get built, just skip it.
	test -d $dir || continue
	mkdir -p %{buildroot}%{_libexecdir}/kselftests/$dir
	find $dir -maxdepth 1 -type f \( -executable -o -name '*.py' -o -name settings -o \
		-name 'btf_dump_test_case_*.c' -o -name '*.ko' -o \
		-name '*.o' -exec sh -c 'readelf -h "{}" | grep -q "^  Machine:.*BPF"' \; \) -print0 | \
	xargs -0 cp -t %{buildroot}%{_libexecdir}/kselftests/$dir || true
done
%buildroot_save_unstripped "usr/libexec/kselftests/bpf/test_progs"
%buildroot_save_unstripped "usr/libexec/kselftests/bpf/test_progs-no_alu32"
popd
export -n BPFTOOL
%endif

%if %{with_doc}
# Make the HTML pages.
%{__make} PYTHON=/usr/bin/python3 htmldocs || %{doc_build_fail}

# sometimes non-world-readable files sneak into the kernel source tree
chmod -R a=rX Documentation
find Documentation -type d | xargs chmod u+w
%endif

# Module signing (modsign)
#
# This must be run _after_ find-debuginfo.sh runs, otherwise that will strip
# the signature off of the modules.
#
# Don't sign modules for the zfcpdump variant as it is monolithic.

%define __modsign_install_post \
  if [ "%{signmodules}" -eq "1" ]; then \
    echo "Signing kernel modules ..." \
    modules_dirs="$(shopt -s nullglob; echo $RPM_BUILD_ROOT/lib/modules/%{KVERREL}*)" \
    for modules_dir in $modules_dirs; do \
        variant_suffix="${modules_dir#$RPM_BUILD_ROOT/lib/modules/%{KVERREL}}" \
        [ "$variant_suffix" == "+zfcpdump" ] && continue \
        echo "Signing modules for %{KVERREL}${variant_suffix}" \
        %{modsign_cmd} certs/signing_key.pem.sign${variant_suffix} certs/signing_key.x509.sign${variant_suffix} $modules_dir/ \
    done \
  fi \
  if [ "%{zipmodules}" -eq "1" ]; then \
    echo "Compressing kernel modules ..." \
    find $RPM_BUILD_ROOT/lib/modules/ -type f -name '*.ko' | xargs -n 16 -P${RPM_BUILD_NCPUS} -r %compression %compression_flags; \
  fi \
%{nil}

###
### Special hacks for debuginfo subpackages.
###

# This macro is used by %%install, so we must redefine it before that.
%define debug_package %{nil}

%if %{with_debuginfo}

%ifnarch noarch %{nobuildarches}
%global __debug_package 1
%files -f debugfiles.list debuginfo-common-%{_target_cpu}
%endif

%endif

# We don't want to package debuginfo for self-tests and samples but
# we have to delete them to avoid an error messages about unpackaged
# files.
# Delete the debuginfo for kernel-devel files
%define __remove_unwanted_dbginfo_install_post \
  if [ "%{with_selftests}" -ne "0" ]; then \
    rm -rf $RPM_BUILD_ROOT/usr/lib/debug/usr/libexec/ksamples; \
    rm -rf $RPM_BUILD_ROOT/usr/lib/debug/usr/libexec/kselftests; \
  fi \
  rm -rf $RPM_BUILD_ROOT/usr/lib/debug/usr/src; \
%{nil}

#
# Disgusting hack alert! We need to ensure we sign modules *after* all
# invocations of strip occur, which is in __debug_install_post if
# find-debuginfo.sh runs, and __os_install_post if not.
#
%define __spec_install_post \
  %{?__debug_package:%{__debug_install_post}}\
  %{__arch_install_post}\
  %{__os_install_post}\
  %{__remove_unwanted_dbginfo_install_post}\
  %{__restore_unstripped_root_post}\
  %{__modsign_install_post}

###
### install
###

%install

cd linux-%{KVERREL}

%if %{with_doc}
docdir=$RPM_BUILD_ROOT%{_datadir}/doc/kernel-doc-%{specversion}-%{pkgrelease}

# copy the source over
mkdir -p $docdir
tar -h -f - --exclude=man --exclude='.*' -c Documentation | tar xf - -C $docdir

# with_doc
%endif

# We have to do the headers install before the tools install because the
# kernel headers_install will remove any header files in /usr/include that
# it doesn't install itself.

%if %{with_headers}
# Install kernel headers
%{__make} ARCH=%{hdrarch} INSTALL_HDR_PATH=$RPM_BUILD_ROOT/usr headers_install

find $RPM_BUILD_ROOT/usr/include \
     \( -name .install -o -name .check -o \
        -name ..install.cmd -o -name ..check.cmd \) -delete

%endif

%if %{with_cross_headers}
HDR_ARCH_LIST='arm64 powerpc s390 x86 riscv64'
mkdir -p $RPM_BUILD_ROOT/usr/tmp-headers

for arch in $HDR_ARCH_LIST; do
	mkdir $RPM_BUILD_ROOT/usr/tmp-headers/arch-${arch}
	%{__make} ARCH=${arch} INSTALL_HDR_PATH=$RPM_BUILD_ROOT/usr/tmp-headers/arch-${arch} headers_install
done

find $RPM_BUILD_ROOT/usr/tmp-headers \
     \( -name .install -o -name .check -o \
        -name ..install.cmd -o -name ..check.cmd \) -delete

# Copy all the architectures we care about to their respective asm directories
for arch in $HDR_ARCH_LIST ; do
	mkdir -p $RPM_BUILD_ROOT/usr/${arch}-linux-gnu/include
	mv $RPM_BUILD_ROOT/usr/tmp-headers/arch-${arch}/include/* $RPM_BUILD_ROOT/usr/${arch}-linux-gnu/include/
done

rm -rf $RPM_BUILD_ROOT/usr/tmp-headers
%endif

%if %{with_kernel_abi_stablelists}
# kabi directory
INSTALL_KABI_PATH=$RPM_BUILD_ROOT/lib/modules/
mkdir -p $INSTALL_KABI_PATH

# install kabi releases directories
tar -xvf %{SOURCE300} -C $INSTALL_KABI_PATH
# with_kernel_abi_stablelists
%endif

%if %{with_perf}
# perf tool binary and supporting scripts/binaries
%{perf_make} DESTDIR=$RPM_BUILD_ROOT lib=%{_lib} install-bin
# remove the 'trace' symlink.
rm -f %{buildroot}%{_bindir}/trace

# For both of the below, yes, this should be using a macro but right now
# it's hard coded and we don't actually want it anyway right now.
# Whoever wants examples can fix it up!

# remove examples
rm -rf %{buildroot}/usr/lib/perf/examples
rm -rf %{buildroot}/usr/lib/perf/include

# python-perf extension
%{perf_make} DESTDIR=$RPM_BUILD_ROOT install-python_ext

# perf man pages (note: implicit rpm magic compresses them later)
mkdir -p %{buildroot}/%{_mandir}/man1
%{perf_make} DESTDIR=$RPM_BUILD_ROOT install-man

# remove any tracevent files, eg. its plugins still gets built and installed,
# even if we build against system's libtracevent during perf build (by setting
# LIBTRACEEVENT_DYNAMIC=1 above in perf_make macro). Those files should already
# ship with libtraceevent package.
rm -rf %{buildroot}%{_libdir}/traceevent
%endif

%if %{with_tools}
%ifarch %{cpupowerarchs}
%{make} -C tools/power/cpupower DESTDIR=$RPM_BUILD_ROOT libdir=%{_libdir} mandir=%{_mandir} CPUFREQ_BENCH=false install
rm -f %{buildroot}%{_libdir}/*.{a,la}
%find_lang cpupower
mv cpupower.lang ../
%ifarch x86_64
    pushd tools/power/cpupower/debug/x86_64
    install -m755 centrino-decode %{buildroot}%{_bindir}/centrino-decode
    install -m755 powernow-k8-decode %{buildroot}%{_bindir}/powernow-k8-decode
    popd
%endif
chmod 0755 %{buildroot}%{_libdir}/libcpupower.so*
%endif
%ifarch x86_64
   mkdir -p %{buildroot}%{_mandir}/man8
   pushd tools/power/x86/x86_energy_perf_policy
   %{tools_make} DESTDIR=%{buildroot} install
   popd
   pushd tools/power/x86/turbostat
   %{tools_make} DESTDIR=%{buildroot} install
   popd
   pushd tools/power/x86/intel-speed-select
   %{tools_make} DESTDIR=%{buildroot} install
   popd
   pushd tools/arch/x86/intel_sdsi
   %{tools_make} CFLAGS="${RPM_OPT_FLAGS}" DESTDIR=%{buildroot} install
   popd
%endif
pushd tools/thermal/tmon
%{tools_make} INSTALL_ROOT=%{buildroot} install
popd
pushd tools/iio
%{tools_make} DESTDIR=%{buildroot} install
popd
pushd tools/gpio
%{tools_make} DESTDIR=%{buildroot} install
popd
install -m644 -D %{SOURCE2002} %{buildroot}%{_sysconfdir}/logrotate.d/kvm_stat
pushd tools/kvm/kvm_stat
%{__make} INSTALL_ROOT=%{buildroot} install-tools
%{__make} INSTALL_ROOT=%{buildroot} install-man
install -m644 -D kvm_stat.service %{buildroot}%{_unitdir}/kvm_stat.service
popd
# install VM tools
pushd tools/mm/
install -m755 slabinfo %{buildroot}%{_bindir}/slabinfo
install -m755 page_owner_sort %{buildroot}%{_bindir}/page_owner_sort
popd
pushd tools/verification/rv/
%{tools_make} DESTDIR=%{buildroot} install
popd
pushd tools/tracing/rtla/
%{tools_make} DESTDIR=%{buildroot} install
rm -f %{buildroot}%{_bindir}/hwnoise
rm -f %{buildroot}%{_bindir}/osnoise
rm -f %{buildroot}%{_bindir}/timerlat
(cd %{buildroot}

        ln -sf rtla ./%{_bindir}/hwnoise
        ln -sf rtla ./%{_bindir}/osnoise
        ln -sf rtla ./%{_bindir}/timerlat
)
popd
%endif

%if %{with_bpftool}
pushd tools/bpf/bpftool
%{bpftool_make} prefix=%{_prefix} bash_compdir=%{_sysconfdir}/bash_completion.d/ mandir=%{_mandir} install doc-install
popd
%endif

%if %{with_selftests}
pushd samples
install -d %{buildroot}%{_libexecdir}/ksamples
# install bpf samples
pushd bpf
install -d %{buildroot}%{_libexecdir}/ksamples/bpf
find -type f -executable -exec install -m755 {} %{buildroot}%{_libexecdir}/ksamples/bpf \;
install -m755 *.sh %{buildroot}%{_libexecdir}/ksamples/bpf
# test_lwt_bpf.sh compiles test_lwt_bpf.c when run; this works only from the
# kernel tree. Just remove it.
rm %{buildroot}%{_libexecdir}/ksamples/bpf/test_lwt_bpf.sh
install -m644 *_kern.o %{buildroot}%{_libexecdir}/ksamples/bpf || true
install -m644 tcp_bpf.readme %{buildroot}%{_libexecdir}/ksamples/bpf
popd
# install pktgen samples
pushd pktgen
install -d %{buildroot}%{_libexecdir}/ksamples/pktgen
find . -type f -executable -exec install -m755 {} %{buildroot}%{_libexecdir}/ksamples/pktgen/{} \;
find . -type f ! -executable -exec install -m644 {} %{buildroot}%{_libexecdir}/ksamples/pktgen/{} \;
popd
popd
# install mm selftests
pushd tools/testing/selftests/mm
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/mm/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/mm/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/mm/{} \;
popd
# install drivers/net/mlxsw selftests
pushd tools/testing/selftests/drivers/net/mlxsw
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/drivers/net/mlxsw/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/drivers/net/mlxsw/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/drivers/net/mlxsw/{} \;
popd
# install drivers/net/netdevsim selftests
pushd tools/testing/selftests/drivers/net/netdevsim
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/drivers/net/netdevsim/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/drivers/net/netdevsim/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/drivers/net/netdevsim/{} \;
popd
# install drivers/net/bonding selftests
pushd tools/testing/selftests/drivers/net/bonding
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/drivers/net/bonding/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/drivers/net/bonding/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/drivers/net/bonding/{} \;
popd
# install net/forwarding selftests
pushd tools/testing/selftests/net/forwarding
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/net/forwarding/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/net/forwarding/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/net/forwarding/{} \;
popd
# install net/mptcp selftests
pushd tools/testing/selftests/net/mptcp
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/net/mptcp/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/net/mptcp/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/net/mptcp/{} \;
popd
# install tc-testing selftests
pushd tools/testing/selftests/tc-testing
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/tc-testing/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/tc-testing/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/tc-testing/{} \;
popd
# install livepatch selftests
pushd tools/testing/selftests/livepatch
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/livepatch/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/livepatch/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/livepatch/{} \;
popd
# install netfilter selftests
pushd tools/testing/selftests/netfilter
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/netfilter/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/netfilter/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/netfilter/{} \;
popd

# install memfd selftests
pushd tools/testing/selftests/memfd
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/memfd/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/memfd/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/memfd/{} \;
popd
%endif

###
### clean
###

###
### scripts
###

%if %{with_tools}
%post -n %{package_name}-tools-libs
/sbin/ldconfig

%postun -n %{package_name}-tools-libs
/sbin/ldconfig
%endif

#
# This macro defines a %%post script for a kernel*-devel package.
#	%%kernel_devel_post [<subpackage>]
# Note we don't run hardlink if ostree is in use, as ostree is
# a far more sophisticated hardlink implementation.
# https://github.com/projectatomic/rpm-ostree/commit/58a79056a889be8814aa51f507b2c7a4dccee526
#
# The deletion of *.hardlink-temporary files is a temporary workaround
# for this bug in the hardlink binary (fixed in util-linux 2.38):
# https://github.com/util-linux/util-linux/issues/1602
#
%define kernel_devel_post() \
%{expand:%%post %{?1:%{1}-}devel}\
if [ -f /etc/sysconfig/kernel ]\
then\
    . /etc/sysconfig/kernel || exit $?\
fi\
if [ "$HARDLINK" != "no" -a -x /usr/bin/hardlink -a ! -e /run/ostree-booted ] \
then\
    (cd /usr/src/kernels/%{KVERREL}%{?1:+%{1}} &&\
     /usr/bin/find . -type f | while read f; do\
       hardlink -c /usr/src/kernels/*%{?dist}.*/$f $f > /dev/null\
     done;\
     /usr/bin/find /usr/src/kernels -type f -name '*.hardlink-temporary' -delete\
    )\
fi\
%{nil}

#
# This macro defines a %%post script for a kernel*-modules-extra package.
# It also defines a %%postun script that does the same thing.
#	%%kernel_modules_extra_post [<subpackage>]
#
%define kernel_modules_extra_post() \
%{expand:%%post %{?1:%{1}-}modules-extra}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
%{nil}\
%{expand:%%postun %{?1:%{1}-}modules-extra}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
%{nil}

#
# This macro defines a %%post script for a kernel*-modules-internal package.
# It also defines a %%postun script that does the same thing.
#	%%kernel_modules_internal_post [<subpackage>]
#
%define kernel_modules_internal_post() \
%{expand:%%post %{?1:%{1}-}modules-internal}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
%{nil}\
%{expand:%%postun %{?1:%{1}-}modules-internal}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
%{nil}

#
# This macro defines a %%post script for a kernel*-modules-partner package.
# It also defines a %%postun script that does the same thing.
#	%%kernel_modules_partner_post [<subpackage>]
#
%define kernel_modules_partner_post() \
%{expand:%%post %{?1:%{1}-}modules-partner}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
%{nil}\
%{expand:%%postun %{?1:%{1}-}modules-partner}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
%{nil}

%if %{with_realtime}
#
# This macro defines a %%post script for a kernel*-kvm package.
# It also defines a %%postun script that does the same thing.
#	%%kernel_kvm_post [<subpackage>]
#
%define kernel_kvm_post() \
%{expand:%%post %{?1:%{1}-}kvm}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
%{nil}\
%{expand:%%postun %{?1:%{1}-}kvm}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
%{nil}
%endif

#
# This macro defines a %%post script for a kernel*-modules package.
# It also defines a %%postun script that does the same thing.
#	%%kernel_modules_post [<subpackage>]
#
%define kernel_modules_post() \
%{expand:%%post %{?1:%{1}-}modules}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
if [ ! -f %{_localstatedir}/lib/rpm-state/%{name}/installing_core_%{KVERREL}%{?1:+%{1}} ]; then\
	mkdir -p %{_localstatedir}/lib/rpm-state/%{name}\
	touch %{_localstatedir}/lib/rpm-state/%{name}/need_to_run_dracut_%{KVERREL}%{?1:+%{1}}\
fi\
%{nil}\
%{expand:%%postun %{?1:%{1}-}modules}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
%{nil}\
%{expand:%%posttrans %{?1:%{1}-}modules}\
if [ -f %{_localstatedir}/lib/rpm-state/%{name}/need_to_run_dracut_%{KVERREL}%{?1:+%{1}} ]; then\
	rm -f %{_localstatedir}/lib/rpm-state/%{name}/need_to_run_dracut_%{KVERREL}%{?1:+%{1}}\
	echo "Running: dracut -f --kver %{KVERREL}%{?1:+%{1}}"\
	dracut -f --kver "%{KVERREL}%{?1:+%{1}}" || exit $?\
fi\
%{nil}

#
# This macro defines a %%post script for a kernel*-modules-core package.
#	%%kernel_modules_core_post [<subpackage>]
#
%define kernel_modules_core_post() \
%{expand:%%posttrans %{?1:%{1}-}modules-core}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
%{nil}

# This macro defines a %%posttrans script for a kernel package.
#	%%kernel_variant_posttrans [-v <subpackage>] [-u uki-suffix]
# More text can follow to go at the end of this variant's %%post.
#
%define kernel_variant_posttrans(v:u:) \
%{expand:%%posttrans %{?-v:%{-v*}-}%{!?-u*:core}%{?-u*:uki-%{-u*}}}\
%if 0%{!?fedora:1}\
if [ -x %{_sbindir}/weak-modules ]\
then\
    %{_sbindir}/weak-modules --add-kernel %{KVERREL}%{?-v:+%{-v*}} || exit $?\
fi\
%endif\
rm -f %{_localstatedir}/lib/rpm-state/%{name}/installing_core_%{KVERREL}%{?-v:+%{-v*}}\
/bin/kernel-install add %{KVERREL}%{?-v:+%{-v*}} /lib/modules/%{KVERREL}%{?-v:+%{-v*}}/vmlinuz%{?-u:-%{-u*}.efi} || exit $?\
if [[ ! -e "/boot/symvers-%{KVERREL}%{?-v:+%{-v*}}.%compext" ]]; then\
    ln -s "/lib/modules/%{KVERREL}%{?-v:+%{-v*}}/symvers.%compext" "/boot/symvers-%{KVERREL}%{?-v:+%{-v*}}.%compext"\
    if command -v restorecon &>/dev/null; then\
        restorecon "/boot/symvers-%{KVERREL}%{?-v:+%{-v*}}.%compext"\
    fi\
fi\
%{nil}

#
# This macro defines a %%post script for a kernel package and its devel package.
#	%%kernel_variant_post [-v <subpackage>] [-r <replace>]
# More text can follow to go at the end of this variant's %%post.
#
%define kernel_variant_post(v:r:) \
%{expand:%%kernel_devel_post %{?-v*}}\
%{expand:%%kernel_modules_post %{?-v*}}\
%{expand:%%kernel_modules_core_post %{?-v*}}\
%{expand:%%kernel_modules_extra_post %{?-v*}}\
%{expand:%%kernel_modules_internal_post %{?-v*}}\
%if 0%{!?fedora:1}\
%{expand:%%kernel_modules_partner_post %{?-v*}}\
%endif\
%{expand:%%kernel_variant_posttrans %{?-v*:-v %{-v*}}}\
%{expand:%%post %{?-v*:%{-v*}-}core}\
%{-r:\
if [ `uname -i` == "x86_64" -o `uname -i` == "i386" ] &&\
   [ -f /etc/sysconfig/kernel ]; then\
  /bin/sed -r -i -e 's/^DEFAULTKERNEL=%{-r*}$/DEFAULTKERNEL=kernel%{?-v:-%{-v*}}/' /etc/sysconfig/kernel || exit $?\
fi}\
mkdir -p %{_localstatedir}/lib/rpm-state/%{name}\
touch %{_localstatedir}/lib/rpm-state/%{name}/installing_core_%{KVERREL}%{?-v:+%{-v*}}\
%{nil}

#
# This macro defines a %%preun script for a kernel package.
#	%%kernel_variant_preun [-v <subpackage>] -u [uki-suffix]
#
%define kernel_variant_preun(v:u:) \
%{expand:%%preun %{?-v:%{-v*}-}%{!?-u*:core}%{?-u*:uki-%{-u*}}}\
/bin/kernel-install remove %{KVERREL}%{?-v:+%{-v*}} || exit $?\
if [ -x %{_sbindir}/weak-modules ]\
then\
    %{_sbindir}/weak-modules --remove-kernel %{KVERREL}%{?-v:+%{-v*}} || exit $?\
fi\
%{nil}

%if %{with_up_base} && %{with_efiuki}
%kernel_variant_posttrans -u virt
%kernel_variant_preun -u virt
%endif

%if %{with_up_base}
%kernel_variant_preun
%kernel_variant_post -r kernel-smp
%endif

%if %{with_zfcpdump}
%kernel_variant_preun -v zfcpdump
%kernel_variant_post -v zfcpdump
%endif

%if %{with_up} && %{with_debug} && %{with_efiuki}
%kernel_variant_posttrans -v debug -u virt
%kernel_variant_preun -v debug -u virt
%endif

%if %{with_up} && %{with_debug}
%kernel_variant_preun -v debug
%kernel_variant_post -v debug
%endif

%if %{with_arm64_16k_base}
%kernel_variant_preun -v 16k
%kernel_variant_post -v 16k
%endif

%if %{with_debug} && %{with_arm64_16k}
%kernel_variant_preun -v 16k-debug
%kernel_variant_post -v 16k-debug
%endif

%if %{with_arm64_64k_base}
%kernel_variant_preun -v 64k
%kernel_variant_post -v 64k
%endif

%if %{with_debug} && %{with_arm64_64k}
%kernel_variant_preun -v 64k-debug
%kernel_variant_post -v 64k-debug
%endif

%if %{with_realtime_base}
%kernel_variant_preun -v rt
%kernel_variant_post -v rt -r (kernel|kernel-smp)
%kernel_kvm_post rt
%endif

%if %{with_realtime} && %{with_debug}
%kernel_variant_preun -v rt-debug
%kernel_variant_post -v rt-debug
%kernel_kvm_post rt-debug
%endif

###
### file lists
###

%if %{with_headers}
%files headers
/usr/include/*
%exclude %{_includedir}/cpufreq.h
%endif

%if %{with_cross_headers}
%files cross-headers
/usr/*-linux-gnu/include/*
%endif

%if %{with_kernel_abi_stablelists}
%files -n %{package_name}-abi-stablelists
/lib/modules/kabi-*
%endif

%if %{with_kabidw_base}
%ifarch x86_64 s390x ppc64 ppc64le aarch64 riscv64
%files kernel-kabidw-base-internal
%defattr(-,root,root)
/kabidw-base/%{_target_cpu}/*
%endif
%endif

# only some architecture builds need kernel-doc
%if %{with_doc}
%files doc
%defattr(-,root,root)
%{_datadir}/doc/kernel-doc-%{specversion}-%{pkgrelease}/Documentation/*
%dir %{_datadir}/doc/kernel-doc-%{specversion}-%{pkgrelease}/Documentation
%dir %{_datadir}/doc/kernel-doc-%{specversion}-%{pkgrelease}
%endif

%if %{with_perf}
%files -n perf
%{_bindir}/perf
%{_libdir}/libperf-jvmti.so
%dir %{_libexecdir}/perf-core
%{_libexecdir}/perf-core/*
%{_datadir}/perf-core/*
%{_mandir}/man[1-8]/perf*
%{_sysconfdir}/bash_completion.d/perf
%doc linux-%{KVERREL}/tools/perf/Documentation/examples.txt
%{_docdir}/perf-tip/tips.txt

%files -n python3-perf
%{python3_sitearch}/*

%if %{with_debuginfo}
%files -f perf-debuginfo.list -n perf-debuginfo

%files -f python3-perf-debuginfo.list -n python3-perf-debuginfo
%endif
# with_perf
%endif

%if %{with_tools}
%ifnarch %{cpupowerarchs}
%files -n %{package_name}-tools
%else
%files -n %{package_name}-tools -f cpupower.lang
%{_bindir}/cpupower
%{_datadir}/bash-completion/completions/cpupower
%ifarch x86_64
%{_bindir}/centrino-decode
%{_bindir}/powernow-k8-decode
%endif
%{_mandir}/man[1-8]/cpupower*
%ifarch x86_64
%{_bindir}/x86_energy_perf_policy
%{_mandir}/man8/x86_energy_perf_policy*
%{_bindir}/turbostat
%{_mandir}/man8/turbostat*
%{_bindir}/intel-speed-select
%{_sbindir}/intel_sdsi
%endif
# cpupowerarchs
%endif
%{_bindir}/tmon
%{_bindir}/iio_event_monitor
%{_bindir}/iio_generic_buffer
%{_bindir}/lsiio
%{_bindir}/lsgpio
%{_bindir}/gpio-hammer
%{_bindir}/gpio-event-mon
%{_bindir}/gpio-watch
%{_mandir}/man1/kvm_stat*
%{_bindir}/kvm_stat
%{_unitdir}/kvm_stat.service
%config(noreplace) %{_sysconfdir}/logrotate.d/kvm_stat
%{_bindir}/page_owner_sort
%{_bindir}/slabinfo

%if %{with_debuginfo}
%files -f %{package_name}-tools-debuginfo.list -n %{package_name}-tools-debuginfo
%endif

%ifarch %{cpupowerarchs}
%files -n %{package_name}-tools-libs
%{_libdir}/libcpupower.so.1
%{_libdir}/libcpupower.so.0.0.1

%files -n %{package_name}-tools-libs-devel
%{_libdir}/libcpupower.so
%{_includedir}/cpufreq.h
%endif

%files -n rtla
%{_bindir}/rtla
%{_bindir}/hwnoise
%{_bindir}/osnoise
%{_bindir}/timerlat
%{_mandir}/man1/rtla-hwnoise.1.gz
%{_mandir}/man1/rtla-osnoise-hist.1.gz
%{_mandir}/man1/rtla-osnoise-top.1.gz
%{_mandir}/man1/rtla-osnoise.1.gz
%{_mandir}/man1/rtla-timerlat-hist.1.gz
%{_mandir}/man1/rtla-timerlat-top.1.gz
%{_mandir}/man1/rtla-timerlat.1.gz
%{_mandir}/man1/rtla.1.gz

%files -n rv
%{_bindir}/rv
%{_mandir}/man1/rv-list.1.gz
%{_mandir}/man1/rv-mon-wip.1.gz
%{_mandir}/man1/rv-mon-wwnr.1.gz
%{_mandir}/man1/rv-mon.1.gz
%{_mandir}/man1/rv.1.gz

# with_tools
%endif

%if %{with_bpftool}
%files -n bpftool
%{_sbindir}/bpftool
%{_sysconfdir}/bash_completion.d/bpftool
%{_mandir}/man8/bpftool-cgroup.8.gz
%{_mandir}/man8/bpftool-gen.8.gz
%{_mandir}/man8/bpftool-iter.8.gz
%{_mandir}/man8/bpftool-link.8.gz
%{_mandir}/man8/bpftool-map.8.gz
%{_mandir}/man8/bpftool-prog.8.gz
%{_mandir}/man8/bpftool-perf.8.gz
%{_mandir}/man8/bpftool.8.gz
%{_mandir}/man8/bpftool-net.8.gz
%{_mandir}/man8/bpftool-feature.8.gz
%{_mandir}/man8/bpftool-btf.8.gz
%{_mandir}/man8/bpftool-struct_ops.8.gz

%if %{with_debuginfo}
%files -f bpftool-debuginfo.list -n bpftool-debuginfo
%defattr(-,root,root)
%endif
%endif

%if %{with_selftests}
%files selftests-internal
%{_libexecdir}/ksamples
%{_libexecdir}/kselftests
%endif

# empty meta-package
%if %{with_up_base}
%ifnarch %nobuildarches noarch
%files
%endif
%endif

# This is %%{image_install_path} on an arch where that includes ELF files,
# or empty otherwise.
%define elf_image_install_path %{?kernel_image_elf:%{image_install_path}}

#
# This macro defines the %%files sections for a kernel package
# and its devel and debuginfo packages.
#	%%kernel_variant_files [-k vmlinux] <use_vdso> <condition> <subpackage>
#
%define kernel_variant_files(k:) \
%if %{2}\
%{expand:%%files %{?1:-f kernel-%{?3:%{3}-}ldsoconf.list} %{?3:%{3}-}core}\
%{!?_licensedir:%global license %%doc}\
%%license linux-%{KVERREL}/COPYING-%{version}-%{release}\
/lib/modules/%{KVERREL}%{?3:+%{3}}/%{?-k:%{-k*}}%{!?-k:vmlinuz}\
%ghost /%{image_install_path}/%{?-k:%{-k*}}%{!?-k:vmlinuz}-%{KVERREL}%{?3:+%{3}}\
/lib/modules/%{KVERREL}%{?3:+%{3}}/.vmlinuz.hmac \
%ghost /%{image_install_path}/.vmlinuz-%{KVERREL}%{?3:+%{3}}.hmac \
%ifarch aarch64 riscv64\
/lib/modules/%{KVERREL}%{?3:+%{3}}/dtb \
%ghost /%{image_install_path}/dtb-%{KVERREL}%{?3:+%{3}} \
%endif\
%attr(0600, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/System.map\
%ghost %attr(0600, root, root) /boot/System.map-%{KVERREL}%{?3:+%{3}}\
%dir /lib/modules\
%dir /lib/modules/%{KVERREL}%{?3:+%{3}}\
/lib/modules/%{KVERREL}%{?3:+%{3}}/symvers.%compext\
/lib/modules/%{KVERREL}%{?3:+%{3}}/config\
/lib/modules/%{KVERREL}%{?3:+%{3}}/modules.builtin*\
%ghost %attr(0600, root, root) /boot/symvers-%{KVERREL}%{?3:+%{3}}.%compext\
%ghost %attr(0600, root, root) /boot/initramfs-%{KVERREL}%{?3:+%{3}}.img\
%ghost %attr(0644, root, root) /boot/config-%{KVERREL}%{?3:+%{3}}\
%{expand:%%files -f kernel-%{?3:%{3}-}modules-core.list %{?3:%{3}-}modules-core}\
%dir /lib/modules/%{KVERREL}%{?3:+%{3}}/kernel\
/lib/modules/%{KVERREL}%{?3:+%{3}}/build\
/lib/modules/%{KVERREL}%{?3:+%{3}}/source\
/lib/modules/%{KVERREL}%{?3:+%{3}}/updates\
/lib/modules/%{KVERREL}%{?3:+%{3}}/weak-updates\
/lib/modules/%{KVERREL}%{?3:+%{3}}/systemtap\
%{_datadir}/doc/kernel-keys/%{KVERREL}%{?3:+%{3}}\
%if %{1}\
/lib/modules/%{KVERREL}%{?3:+%{3}}/vdso\
%endif\
/lib/modules/%{KVERREL}%{?3:+%{3}}/modules.block\
/lib/modules/%{KVERREL}%{?3:+%{3}}/modules.drm\
/lib/modules/%{KVERREL}%{?3:+%{3}}/modules.modesetting\
/lib/modules/%{KVERREL}%{?3:+%{3}}/modules.networking\
/lib/modules/%{KVERREL}%{?3:+%{3}}/modules.order\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.alias\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.alias.bin\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.builtin.alias.bin\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.builtin.bin\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.dep\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.dep.bin\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.devname\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.softdep\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.symbols\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.symbols.bin\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.weakdep\
%{expand:%%files -f kernel-%{?3:%{3}-}modules.list %{?3:%{3}-}modules}\
%{expand:%%files %{?3:%{3}-}devel}\
%defverify(not mtime)\
/usr/src/kernels/%{KVERREL}%{?3:+%{3}}\
%{expand:%%files %{?3:%{3}-}devel-matched}\
%{expand:%%files -f kernel-%{?3:%{3}-}modules-extra.list %{?3:%{3}-}modules-extra}\
%config(noreplace) /etc/modprobe.d/*-blacklist.conf\
%{expand:%%files %{?3:%{3}-}modules-internal}\
/lib/modules/%{KVERREL}%{?3:+%{3}}/internal\
%if 0%{!?fedora:1}\
%{expand:%%files %{?3:%{3}-}modules-partner}\
/lib/modules/%{KVERREL}%{?3:+%{3}}/partner\
%endif\
%if %{with_debuginfo}\
%ifnarch noarch\
%{expand:%%files -f debuginfo%{?3}.list %{?3:%{3}-}debuginfo}\
%endif\
%endif\
%if "%{3}" == "rt" || "%{3}" == "rt-debug"\
%{expand:%%files %{?3:%{3}-}kvm}\
/lib/modules/%{KVERREL}%{?3:+%{3}}/kvm\
%else\
%if %{with_efiuki}\
%{expand:%%files %{?3:%{3}-}uki-virt}\
%attr(0600, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/System.map\
/lib/modules/%{KVERREL}%{?3:+%{3}}/symvers.%compext\
/lib/modules/%{KVERREL}%{?3:+%{3}}/config\
/lib/modules/%{KVERREL}%{?3:+%{3}}/modules.builtin*\
/lib/modules/%{KVERREL}%{?3:+%{3}}/%{?-k:%{-k*}}%{!?-k:vmlinuz}-virt.efi\
%ghost /%{image_install_path}/efi/EFI/Linux/%{?-k:%{-k*}}%{!?-k:*}-%{KVERREL}%{?3:+%{3}}.efi\
%endif\
%endif\
%if %{?3:1} %{!?3:0}\
%{expand:%%files %{3}}\
%endif\
%if %{with_gcov}\
%ifnarch %nobuildarches noarch\
%{expand:%%files -f kernel-%{?3:%{3}-}gcov.list %{?3:%{3}-}gcov}\
%endif\
%endif\
%endif\
%{nil}

%kernel_variant_files %{_use_vdso} %{with_up_base}
%if %{with_up}
%kernel_variant_files %{_use_vdso} %{with_debug} debug
%endif
%if %{with_arm64_16k}
%kernel_variant_files %{_use_vdso} %{with_debug} 16k-debug
%endif
%if %{with_arm64_64k}
%kernel_variant_files %{_use_vdso} %{with_debug} 64k-debug
%endif
%kernel_variant_files %{_use_vdso} %{with_realtime_base} rt
%if %{with_realtime}
%kernel_variant_files %{_use_vdso} %{with_debug} rt-debug
%endif
%if %{with_debug_meta}
%files debug
%files debug-core
%files debug-devel
%files debug-devel-matched
%files debug-modules
%files debug-modules-core
%files debug-modules-extra
%if %{with_arm64_16k}
%files 16k-debug
%files 16k-debug-core
%files 16k-debug-devel
%files 16k-debug-devel-matched
%files 16k-debug-modules
%files 16k-debug-modules-extra
%endif
%if %{with_arm64_64k}
%files 64k-debug
%files 64k-debug-core
%files 64k-debug-devel
%files 64k-debug-devel-matched
%files 64k-debug-modules
%files 64k-debug-modules-extra
%endif
%endif
%kernel_variant_files %{_use_vdso} %{with_zfcpdump} zfcpdump
%kernel_variant_files %{_use_vdso} %{with_arm64_16k_base} 16k
%kernel_variant_files %{_use_vdso} %{with_arm64_64k_base} 64k

%define kernel_variant_ipaclones(k:) \
%if %{1}\
%if %{with_ipaclones}\
%{expand:%%files %{?2:%{2}-}ipaclones-internal}\
%defattr(-,root,root)\
%defverify(not mtime)\
/usr/src/kernels/%{KVERREL}%{?2:+%{2}}-ipaclones\
%endif\
%endif\
%{nil}

%kernel_variant_ipaclones %{with_up_base}

# plz don't put in a version string unless you're going to tag
# and build.
#
#
%changelog
* Sun Jul 6 2025 Jason Montleon <jason@montleon.com> [6.6.96-200.eswin]
- Add rockos patches up to Jul 6, 2025
- Add back 1.8 GHz for StarPro64

* Fri Mar 28 2025 Jason Montleon <jason@montleon.com> [6.6.85-200.eswin]
- Add rockos patches up to Mar 28, 2025 

* Sat Mar 22 2025 Jason Montleon <jason@montleon.com> [6.6.84-200.eswin]
- Add rockos patches up to Mar 21, 2025 

* Wed Feb 26 2025 Jason Montleon <jason@montleon.com> [6.6.79-206.eswin]
- Disable VIDEO_ESWIN_HAE

* Sun Feb 23 2025 Jason Montleon <jason@montleon.com> [6.6.79-205.eswin]
- Enable CONFIG_DEVFREQ_GOV_USERSPACE 

* Sun Feb 23 2025 Jason Montleon <jason@montleon.com> [6.6.79-204.eswin]
- Enable ESWIN_MMZ_VB and other disabled ESWIN options
- Add NPU enabled variants of dtbs (these reserve 6GB of system RAM for the NPU)
- add remainder of dsp ai_driver workarounds so it will build

* Sat Feb 22 2025 Jason Montleon <jason@montleon.com> [6.6.79-203.eswin]
- Remove mmz reserved memory from dtbs

* Sat Feb 22 2025 Jason Montleon <jason@montleon.com> [6.6.79-202.eswin]
- Disable ESWIN_MMZ_VB 

* Sat Feb 22 2025 Jason Montleon <jason@montleon.com> [6.6.79-201.eswin]
- Disable PM. It breaks sd card detect

* Tue Feb 18 2025 Jason Montleon <jason@montleon.com> [6.6.79-200.eswin]
- Reduce critical temp to 85c
- Modify some config options

* Tue Feb 18 2025 Jason Montleon <jason@montleon.com> [6.6.78-200.megrez]
- Switch to using github.com/rockos-riscv/rockos-kernel

* Thu Jan 23 2025 Jason Montleon <jason@montleon.com> [6.6.74-200.eswin_1230]
- Add fix: modify critical temperature patch

* Fri Dec 27 2024 Jason Montleon <jason@montleon.com> [6.6.68-200.eswin_1230]
- Update to eswin 1230

* Thu Dec 05 2024 Jason Montleon <jason@montleon.com> [6.6.65-201.eswin_1130]
- Switch riscv target to vmlinuz.efi

* Thu Dec 05 2024 Jason Montleon <jason@montleon.com> [6.6.63-212.eswin_1130]
- First version that boots with working ethernet.

* Sun Dec 03 2023 David Abdurachmanov <davidlt@rivosinc.com> [6.6.4-0.0.riscv64]
- Add support for riscv64

* Sun Dec 03 2023 Justin M. Forbes <jforbes@fedoraproject.org> [6.6.4-0]
- redhat: Fix macro for kernel-uki-virt flavor (Neal Gompa)
- Change the uki reqs for Fedora (Justin M. Forbes)
- Linux v6.6.4

* Tue Nov 28 2023 Justin M. Forbes <jforbes@fedoraproject.org> [6.6.3-0]
- Add BugsFixed for 6.6.3 (Justin M. Forbes)
- Update BugsFixed (Justin M. Forbes)
- Turn on USB_DWC3 for Fedora (rhbz 2250955) (Justin M. Forbes)
- Revert "netfilter: nf_tables: remove catchall element in GC sync path" (Justin M. Forbes)
- More BugsFixed (Justin M. Forbes)
- netfilter: nf_tables: remove catchall element in GC sync path (Pablo Neira Ayuso)
- frop the build number back to 200 for fedora-srpm.sh (Justin M. Forbes)
- ACPI: video: Use acpi_device_fix_up_power_children() (Hans de Goede)
- ACPI: PM: Add acpi_device_fix_up_power_children() function (Hans de Goede)
- Linux v6.6.3

* Mon Nov 20 2023 Justin M. Forbes <jforbes@fedoraproject.org> [6.6.2-0]
- Add bug for AMD ACPI alarm (Justin M. Forbes)
- rtc: cmos: Use ACPI alarm for non-Intel x86 systems too (Mario Limonciello)
- Add bluetooth fixes to BugsFixed (Justin M. Forbes)
- Drop F37 from release targets as it will not rebase to 6.6 (Justin M. Forbes)
- Linux v6.6.2

* Wed Nov 08 2023 Justin M. Forbes <jforbes@fedoraproject.org> [6.6.1-0]
- drivers/firmware: skip simpledrm if nvidia-drm.modeset=1 is set (Javier Martinez Canillas)
- Added required files for rebase (Augusto Caringi)
- Reset RHEL_RELEASE for rebase (Justin M. Forbes)
- [Scheduled job] Catch config mismatches early during upstream merge (Don Zickus)
- redhat/self-test: Update data for KABI xz change (Prarit Bhargava)
- redhat/scripts: Switch KABI tarballs to xz (Prarit Bhargava)
- redhat/kernel.spec.template: Switch KABI compression to xz (Prarit Bhargava)
- redhat: self-test: Use a more complete SRPM file suffix (Andrew Halaney)
- redhat: makefile: remove stray rpmbuild --without (Eric Chanudet)
- Linux v6.6.1

* Mon Oct 30 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-61]
- Linux v6.6.0

* Sun Oct 29 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc7.2af9b20dbb39.60]
- Linux v6.6.0-0.rc7.2af9b20dbb39

* Sat Oct 28 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc7.56567a20b22b.59]
- Consolidate configs into common for 6.6 (Justin M. Forbes)
- Linux v6.6.0-0.rc7.56567a20b22b

* Fri Oct 27 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc7.750b95887e56.58]
- Linux v6.6.0-0.rc7.750b95887e56

* Thu Oct 26 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc7.611da07b89fd.57]
- Updated Fedora configs (Justin M. Forbes)
- Turn on UFSHCD for Fedora x86 (Justin M. Forbes)
- Linux v6.6.0-0.rc7.611da07b89fd

* Wed Oct 25 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc7.4f82870119a4.56]
- redhat: configs: generic: x86: Disable CONFIG_VIDEO_OV01A10 for x86 platform (Hans de Goede)
- Linux v6.6.0-0.rc7.4f82870119a4

* Tue Oct 24 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc7.d88520ad73b7.55]
- redhat: remove pending-rhel CONFIG_XFS_ASSERT_FATAL file (Patrick Talbert)
- New configs in fs/xfs (Fedora Kernel Team)
- crypto: rng - Override drivers/char/random in FIPS mode (Herbert Xu)
- random: Add hook to override device reads and getrandom(2) (Herbert Xu)
- Linux v6.6.0-0.rc7.d88520ad73b7

* Mon Oct 23 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc7.54]
- Linux v6.6.0-0.rc7

* Sun Oct 22 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc6.1acfd2bd3f0d.53]
- Linux v6.6.0-0.rc6.1acfd2bd3f0d

* Sat Oct 21 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc6.9c5d00cb7b6b.52]
- Linux v6.6.0-0.rc6.9c5d00cb7b6b

* Fri Oct 20 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc6.ce55c22ec8b2.51]
- redhat/configs: share CONFIG_ARM64_ERRATUM_2966298 between rhel and fedora (Mark Salter)
- configs: Remove S390 IOMMU config options that no longer exist (Jerry Snitselaar)
- redhat: docs: clarify where bugs and issues are created (Scott Weaver)
- redhat/scripts/rh-dist-git.sh does not take any arguments: fix error message (Denys Vlasenko)
- Add target_branch for gen_config_patches.sh (Don Zickus)
- Linux v6.6.0-0.rc6.ce55c22ec8b2

* Thu Oct 19 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc6.dd72f9c7e512.50]
- Linux v6.6.0-0.rc6.dd72f9c7e512

* Wed Oct 18 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc6.06dc10eae55b.49]
- Linux v6.6.0-0.rc6.06dc10eae55b

* Tue Oct 17 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc6.213f891525c2.48]
- redhat: disable kunit by default (Nico Pache)
- redhat/configs: enable the AMD_PMF driver for RHEL (David Arcari)
- Make CONFIG_ADDRESS_MASKING consistent between fedora and rhel (Chris von Recklinghausen)
- CI: add ark-latest baseline job to tag cki-gating for successful pipelines (Michael Hofmann)
- CI: provide child pipelines for CKI container image gating (Michael Hofmann)
- CI: allow to run as child pipeline (Michael Hofmann)
- CI: provide descriptive pipeline name for scheduled pipelines (Michael Hofmann)
- CI: use job templates for variant variables (Michael Hofmann)
- redhat/kernel.spec.template: simplify __modsign_install_post (Jan Stancek)
- Linux v6.6.0-0.rc6.213f891525c2

* Mon Oct 16 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc6.47]
- Linux v6.6.0-0.rc6

* Sun Oct 15 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc5.9a3dad63edbe.46]
- Fedora filter updates after configs (Justin M. Forbes)
- Fedora configs for 6.6 (Justin M. Forbes)
- Linux v6.6.0-0.rc5.9a3dad63edbe

* Sat Oct 14 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc5.727fb8376504.45]
- Linux v6.6.0-0.rc5.727fb8376504

* Fri Oct 13 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc5.10a6e5feccb8.44]
- Linux v6.6.0-0.rc5.10a6e5feccb8

* Thu Oct 12 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc5.401644852d0b.43]
- Linux v6.6.0-0.rc5.401644852d0b

* Wed Oct 11 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc5.1c8b86a3799f.42]
- Linux v6.6.0-0.rc5.1c8b86a3799f

* Tue Oct 10 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc5.41]
- redhat/configs: Freescale Layerscape SoC family (Steve Best)
- Add clang MR/baseline pipelines (Michael Hofmann)

* Mon Oct 09 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc5.40]
- CI: Remove unused kpet_tree_family (Nikolai Kondrashov)
- Linux v6.6.0-0.rc5

* Sun Oct 08 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc4.b9ddbb0cde2a.39]
- Linux v6.6.0-0.rc4.b9ddbb0cde2a

* Sat Oct 07 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc4.82714078aee4.38]
- Linux v6.6.0-0.rc4.82714078aee4

* Fri Oct 06 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc4.b78b18fb8ee1.37]
- Add clang config framework (Don Zickus)
- Apply partial snippet configs to all configs (Don Zickus)
- Remove unpackaged kgcov config files (Don Zickus)
- redhat/configs: enable missing Kconfig options for Qualcomm RideSX4 (Brian Masney)
- enable CONFIG_ADDRESS_MASKING for x86_64 (Chris von Recklinghausen)
- Linux v6.6.0-0.rc4.b78b18fb8ee1

* Thu Oct 05 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc4.3006adf3be79.36]
- Linux v6.6.0-0.rc4.3006adf3be79

* Wed Oct 04 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc4.cbf3a2cb156a.35]
- Linux v6.6.0-0.rc4.cbf3a2cb156a

* Tue Oct 03 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc4.ce36c8b14987.34]
- common: aarch64: enable NXP Flex SPI (Peter Robinson)
- Linux v6.6.0-0.rc4.ce36c8b14987

* Mon Oct 02 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc4.33]
- Linux v6.6.0-0.rc4

* Sun Oct 01 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc3.e402b08634b3.32]
- Linux v6.6.0-0.rc3.e402b08634b3

* Sat Sep 30 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc3.9f3ebbef746f.31]
- fedora: Switch TI_SCI_CLK and TI_SCI_PM_DOMAINS symbols to built-in (Javier Martinez Canillas)
- Linux v6.6.0-0.rc3.9f3ebbef746f

* Fri Sep 29 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc3.9ed22ae6be81.30]
- Linux v6.6.0-0.rc3.9ed22ae6be81

* Thu Sep 28 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc3.633b47cb009d.29]
- Linux v6.6.0-0.rc3.633b47cb009d

* Wed Sep 27 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc3.0e945134b680.28]
- kernel.spec: adjust build option comment (Michael Hofmann)
- kernel.spec: allow to enable arm64_16k variant (Michael Hofmann)
- gitlab-ci: enable build-only pipelines for Rawhide/16k/aarch64 (Michael Hofmann)
- kernel.spec.template: Fix --without bpftool (Prarit Bhargava)
- redhat/configs: NXP BBNSM Power Key Driver (Steve Best)
- redhat/self-test: Update data for cross compile fields (Prarit Bhargava)
- redhat/Makefile.cross: Add message for disabled subpackages (Prarit Bhargava)
- redhat/Makefile.cross: Update cross targets with disabled subpackages (Prarit Bhargava)
- Linux v6.6.0-0.rc3.0e945134b680

* Tue Sep 26 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc3.27]
- Remove XFS_ASSERT_FATAL from pending-fedora (Justin M. Forbes)

* Mon Sep 25 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc3.26]
- Change default pending for XFS_ONLINE_SCRUB_STATSas it now selects XFS_DEBUG (Justin M. Forbes)
- Linux v6.6.0-0.rc3

* Sun Sep 24 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc2.3aba70aed91f.25]
- Linux v6.6.0-0.rc2.3aba70aed91f

* Sat Sep 23 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc2.d90b0276af8f.24]
- Linux v6.6.0-0.rc2.d90b0276af8f

* Fri Sep 22 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc2.27bbf45eae9c.23]
- gitlab-ci: use --with debug/base to select kernel variants (Michael Hofmann)
- kernel.spec: add rpmbuild --without base option (Michael Hofmann)
- Linux v6.6.0-0.rc2.27bbf45eae9c

* Thu Sep 21 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc2.42dc814987c1.22]
- redhat: spec: Fix typo for kernel_variant_preun for 16k-debug flavor (Neal Gompa)
- Linux v6.6.0-0.rc2.42dc814987c1

* Tue Sep 19 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc2.2cf0f7156238.21]
- Linux v6.6.0-0.rc2.2cf0f7156238

* Mon Sep 18 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc2.20]
- Linux v6.6.0-0.rc2

* Sun Sep 17 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc1.f0b0d403eabb.19]
- Linux v6.6.0-0.rc1.f0b0d403eabb

* Sat Sep 16 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc1.57d88e8a5974.18]
- Linux v6.6.0-0.rc1.57d88e8a5974

* Fri Sep 15 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc1.9fdfb15a3dbf.17]
- Turn off appletalk for fedora (Justin M. Forbes)
- Linux v6.6.0-0.rc1.9fdfb15a3dbf

* Thu Sep 14 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc1.aed8aee11130.16]
- Linux v6.6.0-0.rc1.aed8aee11130

* Wed Sep 13 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc1.3669558bdf35.15]
- Linux v6.6.0-0.rc1.3669558bdf35

* Tue Sep 12 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc1.14]
- New configs in drivers/media (Fedora Kernel Team)
- redhat/docs: Add a mention of bugzilla for bugs (Prarit Bhargava)
- Fix the fixup of Fedora release (Don Zickus)

* Mon Sep 11 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc1.13]
- Linux v6.6.0-0.rc1

* Sun Sep 10 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc0.535a265d7f0d.12]
- Linux v6.6.0-0.rc0.535a265d7f0d

* Sat Sep 09 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc0.6099776f9f26.11]
- Linux v6.6.0-0.rc0.6099776f9f26

* Fri Sep 08 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc0.a48fa7efaf11.10]
- Linux v6.6.0-0.rc0.a48fa7efaf11

* Thu Sep 07 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc0.7ba2090ca64e.9]
- Fix Fedora release scheduled job (Don Zickus)
- Move squashfs to kernel-modules-core (Justin M. Forbes)
- redhat: Explicitly disable CONFIG_COPS (Vitaly Kuznetsov)
- redhat: Add dist-check-licenses target (Vitaly Kuznetsov)
- redhat: Introduce "Verify SPDX-License-Identifier tags" selftest (Vitaly Kuznetsov)
- redhat: Use kspdx-tool output for the License: field (Vitaly Kuznetsov)
- Linux v6.6.0-0.rc0.7ba2090ca64e

* Wed Sep 06 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc0.65d6e954e378.8]
- Rename pipeline repo branch and DW tree names (Michael Hofmann)
- Adjust comments that refer to ARK in a Rawhide context (Michael Hofmann)
- Rename variable names starting with ark- to rawhide- (Michael Hofmann)
- Rename trigger-ark to trigger-rawhide (Michael Hofmann)
- Fix up config mismatches for Fedora (Justin M. Forbes)
- Linux v6.6.0-0.rc0.65d6e954e378

* Tue Sep 05 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc0.3f86ed6ec0b3.7]
- redhat/configs: Texas Instruments Inc. K3 multicore SoC architecture (Steve Best)
- Linux v6.6.0-0.rc0.3f86ed6ec0b3

* Mon Sep 04 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc0.708283abf896.6]
- Linux v6.6.0-0.rc0.708283abf896

* Sun Sep 03 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc0.92901222f83d.5]
- Flip CONFIG_VIDEO_V4L2_SUBDEV_API in pending RHEL due to mismatch (Justin M. Forbes)
- Linux v6.6.0-0.rc0.92901222f83d

* Sat Sep 02 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc0.0468be89b3fa.4]
- CONFIG_HW_RANDOM_HISI: move to common and set to m (Scott Weaver)
- Turn off CONFIG_MEMORY_HOTPLUG_DEFAULT_ONLINE for Fedora s390x (Justin M. Forbes)
- Linux v6.6.0-0.rc0.0468be89b3fa

* Fri Sep 01 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc0.99d99825fc07.3.eln130]
- Disable tests for ELN realtime pipelines (Michael Hofmann)
- New configs in mm/Kconfig (Fedora Kernel Team)
- Flip CONFIG_SND_SOC_CS35L56_SDW to m and clean up (Justin M. Forbes)
- Add drm_exec_test to mod-internal.list (Thorsten Leemhuis)
- Add new pending entry for CONFIG_SND_SOC_CS35L56_SDW to fix mismatch (Justin M. Forbes)
- Linux v6.6.0-0.rc0.99d99825fc07

* Thu Aug 31 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc0.b97d64c72259.2.eln130]
- Fix tarball creation logic (Don Zickus)
- redhat: bump libcpupower soname to match upstream (Patrick Talbert)
- Turn on MEMFD_CREATE in pending as it is selected by CONFIG_TMPFS (Justin M. Forbes)
- Linux v6.6.0-0.rc0.b97d64c72259

* Wed Aug 30 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc0.6c1b980a7e79.1.eln130]
- redhat: drop unneeded build-time dependency gcc-plugin-devel (Coiby Xu)
- Reset RHEL release and trim changelog after rebase (Justin M. Forbes)
- Linux v6.6.0-0.rc0.6c1b980a7e79

* Tue Aug 29 2023 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.6.0-0.rc0.1c59d383390f.59.eln130]
- all: x86: move wayward x86 specific config home (Peter Robinson)
- all: de-dupe non standard config options (Peter Robinson)
- all: x86: clean up microcode loading options (Peter Robinson)
- common: remove unnessary CONFIG_SND_MESON_AXG* (Peter Robinson)
- redhat: Fix UKI install with systemd >= 254 (Vitaly Kuznetsov)
- redhat: Use named parameters for kernel_variant_posttrans()/kernel_variant_preun() (Vitaly Kuznetsov)
- redhat/kernel.spec.template: update compression variables to support zstd (Brian Masney)
- Consolidate configs to common for 6.5 (Justin M. Forbes)
- Remove unused config entry for Fedora (Justin M. Forbes)
- redhat/self-test: Remove rpmlint test (Prarit Bhargava)
- Remove the armv7 config directory from Fedora again (Justin M. Forbes)
- Enable CONFIG_EXPERT for both RHEL and Fedora (Justin M. Forbes)
- redhat/configs: Enable CONFIG_DEVICE_PRIVATE on aarch64 (David Hildenbrand) [2231407]
- redhat/configs: disable CONFIG_ROCKCHIP_ERRATUM_3588001 for RHEL (Mark Salter)
- redhat: shellcheck fixes (Prarit Bhargava)
- redhat/configs: enable tegra114 SPI (Mark Salter)
- all: properly cleanup firewire once and for all (Peter Robinson)
- Fix up filters for Fedora (Justin M. Forbes)
- New configs in arch/x86 (Fedora Kernel Team)
- Add an armv7 directory back for the Fedora configs (Justin M. Forbes)
- Fedora 6.5 config updates (Justin M. Forbes)
- Turn off DMABUF_SYSFS_STATS (Justin M. Forbes)
- CI: rawhide_release: switch to using script to push (Don Zickus)
- redhat/self-test: Update self-test data (Prarit Bhargava)
- redhat/scripts/cross-compile: Update download_cross.sh (Prarit Bhargava)
- redhat/Makefile.cross: Remove ARCH selection code (Prarit Bhargava)
- redhat/Makefile.cross: Update script (Prarit Bhargava)
- Fix interruptible non MR jobs (Michael Hofmann)
- all: run evaluate_configs to de-dupe merged aarch64 (Peter Robinson)
- all: arm: merge the arm and arm/aarch64 (Peter Robinson)
- fedora: remove ARMv7 AKA armhfp configurations (Peter Robinson)
- fedora: remove ARMv7 AKA armhfp support (Peter Robinson)
- redhat/configs: enable CONFIG_VIRTIO_MEM on aarch64 (David Hildenbrand) [2044155]
- redhat/configs: enable CONFIG_MEMORY_HOTREMOVE aarch64 (David Hildenbrand) [2062054]
- redhat: Add arm64-16k kernel flavor scaffold for 16K page-size'd AArch64 (Neal Gompa)
- fedora: enable i3c on aarch64 (Peter Robinson)
- redhat/configs: Remove `CONFIG_HZ_1000 is not set` for aarch64 (Enric Balletbo i Serra)
- redhat/configs: turn on the framework for SPI NOR for ARM (Steve Best)
- configs: add new ChromeOS UART driver (Mark Langsdorf)
- configs: add new ChromeOS Human Presence Sensor (Mark Langsdorf)
- redhat/configs: Enable CONFIG_NVIDIA_WMI_EC_BACKLIGHT for both Fedora and RHEL (Kate Hsuan)
- redhat/configs: Texas Instruments INA3221 driver (Steve Best)
- arm: i.MX: Some minor NXP i.MX cleanups (Peter Robinson)
- Description: Set config for Tegra234 pinctrl driver (Joel Slebodnick)
- Update RPM Scriptlet for kernel-install Changes (Jonathan Steffan)
- [CI] add exit 0 to the end of CI scripts (Don Zickus)
- redhat: configs: Disable CONFIG_CRYPTO_STATS since performance issue for storage (Kate Hsuan) [2227793]
- Remove obsolete variable from gitlab-ci.yml (Ondrej Kinst)
- redhat/configs: Move GVT-g to Fedora only (Alex Williamson)
- [CI] Make sure we are on correct branch before running script (Don Zickus)
- CI: ark-update-configs: sync push command and output (Don Zickus)
- CI: ark-update-configs: misc changes (Don Zickus)
- CI: sync ark-create-release push commands with output (Don Zickus)
- CI: ark-create-release: Add a robust check if nothing changed (Don Zickus)
- CI: Remove legacy tag check cruft (Don Zickus)
- CI: Introduce simple environment script (Don Zickus)
- redhat/configs: Disable FIREWIRE for RHEL (Prarit Bhargava)
- redhat/scripts/rh-dist-git.sh: print list of uploaded files (Denys Vlasenko)
- redhat/scripts/expand_srpm.sh: add missing function, robustify (Denys Vlasenko)
- redhat: Enable HSR and PRP (Felix Maurer)
- redhat/scripts/rh-dist-git.sh: fix outdated message and comment (Denys Vlasenko)
- redhat/configs: Disable CONFIG_I8K (Prarit Bhargava)
- Make sure posttrans script doesn't fail if restorecon is not installed (Daan De Meyer)
- Update filters for new config items (Justin M. Forbes)
- More Fedora 6.5 configs (Justin M. Forbes)
- redhat/configs: disable pre-UVC cameras for RHEL on aarch64 (Dean Nelson)
- redhat/configs: enable CONFIG_MEDIA_SUPPORT for RHEL on aarch64 (Dean Nelson)
- move ownership of /lib/modules/<ver>/ to kernel-core (Thorsten Leemhuis)
- Let kernel-modules-core own the files depmod generates. (Thorsten Leemhuis)
- redhat: configs: Enable CONFIG_TYPEC_STUSB160X for rhel on aarch64 (Desnes Nunes)
- Add filters for ptp_dfl_tod on Fedora (Justin M. Forbes)
- Fedora 6.5 configs part 1 (Justin M. Forbes)
- fedora: enable CONFIG_ZYNQMP_IPI_MBOX as a builtin in pending-fedora (Patrick Talbert)
- fedora: arm: some minor updates (Peter Robinson)
- fedora: bluetooth: enable AOSP extensions (Peter Robinson)
- fedora: wifi: tweak ZYDAS WiFI config options (Peter Robinson)
- scsi: sd: Add "probe_type" module parameter to allow synchronous probing (Ewan D. Milne) [2140017]
- redhat/configs: allow IMA to use MOK keys (Coiby Xu)
- Simplify documentation jobs (Michael Hofmann)
- Auto-cancel pipelines only on MRs (Michael Hofmann)
- CI: Call script directly (Don Zickus)
- CI: Remove stale TAG and Makefile cruft (Don Zickus)
- CI: Move os-build tracking to common area (Don Zickus)
- redhat: use the eln builder for daily jobs (Patrick Talbert)
- redhat: set CONFIG_XILINX_WINDOW_WATCHDOG as disabled in pending (Patrick Talbert)
- Add baseline ARK/ELN pipelines (Michael Hofmann)
- Simplify job rules (Michael Hofmann)
- Build ELN srpm for bot changes (Michael Hofmann)
- Run RH selftests for ELN (Michael Hofmann)
- Simplify job templates (Michael Hofmann)
- Extract rules to allow orthogonal configuration (Michael Hofmann)
- Require ELN pipelines if started automatically (Michael Hofmann)
- Add ARK debug pipeline (Michael Hofmann)
- Extract common parts of child pipeline job (Michael Hofmann)
- Move ARK pipeline variables into job template (Michael Hofmann)
- Simplify ARK pipeline rules (Michael Hofmann)
- Change pathfix.py to %%py3_shebang_fix (Justin M. Forbes)
- Turn on NET_VENDOR_QUALCOMM for Fedora to enable rmnet (Justin M. Forbes)
- redhat: add intel-m10-bmc-hwmon to filter-modules singlemods list (Patrick Talbert)
- fedira: enable pending-fedora CONFIG_CPUFREQ_DT_PLATDEV as a module (Patrick Talbert)
- redhat: fix the 'eln BUILD_TARGET' self-test (Patrick Talbert)
- redhat: update the self-test-data (Patrick Talbert)
- redhat: remove trailing space in dist-dump-variables output (Patrick Talbert)
- Allow ELN pipelines failures (Michael Hofmann)
- Enable cs-like CI (Michael Hofmann)
- Allow to auto-cancel redundant pipelines (Michael Hofmann)
- Remove obsolete unused trigger variable (Michael Hofmann)
- Fix linter warnings in .gitlab-ci.yml (Michael Hofmann)
- config: wifi: debug options for ath11k, brcm80211 and iwlwifi (Íñigo Huguet)
- redhat: allow dbgonly cross builds (Jan Stancek)
- redhat/configs: Clean up x86-64 call depth tracking configs (Waiman Long)
- redhat: move SND configs from pending-rhel to rhel (Patrick Talbert)
- Fix up armv7 configs for Fedora (Justin M. Forbes)
- redhat: Set pending-rhel x86 values for various SND configs (Patrick Talbert)
- redhat: update self-test data (Patrick Talbert)
- redhat: ignore SPECBPFTOOLVERSION/bpftoolversion in self-test create-data.sh (Patrick Talbert)
- fedora/rhel: Move I2C_DESIGNWARE_PLATFORM, I2C_SLAVE, & GPIOLIB from pending (Patrick Talbert)
- redhat/filter-modules.sh.rhel: add needed deps for intel_rapl_tpmi (Jan Stancek)
- fedora: Enable CONFIG_SPI_SLAVE (Patrick Talbert)
- fedora/rhel: enable I2C_DESIGNWARE_PLATFORM, I2C_SLAVE, and GPIOLIB (Patrick Talbert)
- fedora: Enable CONFIG_SPI_SLAVE in fedora-pending (Patrick Talbert)
- redhat: remove extra + (plus) from meta package Requires definitions (Patrick Talbert)
- Add intel-m10-bmc-hwmon to singlemods (Thorsten Leemhuis)
- Add hid-uclogic-test to mod-internal.list (Thorsten Leemhuis)
- Add checksum_kunit.ko to mod-internal.list (Thorsten Leemhuis)
- Add strcat_kunit to mod-internal.list (Thorsten Leemhuis)
- Add input_test to mod-intenal.list (Thorsten Leemhuis)
- Revert "Remove EXPERT from ARCH_FORCE_MAX_ORDER for aarch64" (Justin M. Forbes)
- Reset the release number and dedup the changelog after rebase (Justin M. Forbes)
- Fix up rebase issue with CONFIG_ARCH_FORCE_MAX_ORDER (Justin M. Forbes)
- redhat/kernel.spec.template: Disable 'extracting debug info' messages (Prarit Bhargava)
- kernel/rh_messages.c: Another gcc12 warning on redundant NULL test (Florian Weimer) [2216678]
- redhat: fix signing for realtime and arm64_64k non-debug variants (Jan Stancek)
- redhat: treat with_up consistently (Jan Stancek)
- redhat: make with_realtime opt-in (Jan Stancek)
- redhat/configs: Disable qcom armv7 drippings in the aarch64 tree (Jeremy Linton)
- kernel.spec: drop obsolete ldconfig (Jan Stancek)
- Consolidate config items to common for 6.4 cycle (Justin M. Forbes)
- Turn on CO?NFIg_RMNET for Fedora (Justin M. Forbes)
- redhat/configs: enable CONFIG_MANA_INFINIBAND=m for ARK (Vitaly Kuznetsov)
- redhat/config: common: Enable CONFIG_GPIO_SIM for software development (Kate Hsuan)
- redhat: fix problem with RT kvm modules listed twice in rpm generation (Clark Williams)
- redhat: turn off 64k kernel builds with rtonly (Clark Williams)
- redhat: turn off zfcpdump for rtonly (Clark Williams)
- redhat: don't allow with_rtonly to turn on unsupported arches (Clark Williams)
- redhat: update self-test data for addition of RT and 64k-page variants (Clark Williams)
- redhat: fix realtime and efiuki build conflict (Jan Stancek)
- arm64-64k: Add new kernel variant to RHEL9/CS9 for 64K page-size'd ARM64 (Donald Dutile) [2153073]
- redhat: TEMPORARY set configs to deal with PREEMPT_RT not available (Clark Williams)
- redhat: TEMPORARY default realtime to off (Clark Williams)
- redhat: moved ARM errata configs to arm dir (Clark Williams)
- redhat: RT packaging changes (Clark Williams)
- redhat: miscellaneous commits needed due to CONFIG_EXPERT (Clark Williams)
- redhat: realtime config entries (Clark Williams)
- common: remove deleted USB PCCARD drivers (Peter Robinson)
- fedora: further cleanup of pccard/cardbus subsystem (Peter Robinson)
- common: properly disable PCCARD subsystem (Peter Robinson)
- redhat/configs: arm: enable SERIAL_TEGRA UART for RHEL (Mark Salter)
- redhat/configs: enable CONFIG_X86_AMD_PSTATE_UT (David Arcari)
- redhat/configs: Enable CONFIG_TCG_VTPM_PROXY for RHEL (Štěpán Horáček)
- redhat: do not package *.mod.c generated files (Denys Vlasenko)
- ALSA configuration changes for ARK/RHEL 9.3 (Jaroslav Kysela)
- spec: remove resolve_btfids from kernel-devel (Viktor Malik)
- Fix typo in filter-modules (Justin M. Forbes)
- redhat/configs: Enable CONFIG_INIT_STACK_ALL_ZERO for RHEL (Josh Poimboeuf)
- Remove CONFIG_ARCH_FORCE_MAX_ORDER for aarch64 (Justin M. Forbes)
- Fix up config and filter for PTP_DFL_TOD (Justin M. Forbes)
- redhat/configs: IMX8ULP pinctrl driver (Steve Best)
- redhat/configs: increase CONFIG_FRAME_WARN for Fedora on aarch64 (Brian Masney)
- redhat/configs: add two missing Kconfig options for the Thinkpad x13s (Brian Masney)
- Fedora configs for 6.4 (Justin M. Forbes)
- Change aarch64 CONFIG_ARCH_FORCE_MAX_ORDER to 10 for 4K pages (Justin M. Forbes)
- kernel.spec: remove "RPM_VMLINUX_H=$DevelDir/vmlinux.h" code chunk in %%install (Denys Vlasenko)
- redhat/configs: aarch64: Turn on Display for OnePlus 6 (Eric Curtin)
- redhat/configs: NXP i.MX93 pinctrl, clk, analog to digital converters (Steve Best)
- redhat/configs: Enable CONFIG_SC_GPUCC_8280XP for fedora (Andrew Halaney)
- redhat/configs: Enable CONFIG_QCOM_IPCC for fedora (Andrew Halaney)
- Add rv subpackage for kernel-tools (John Kacur) [2188441]
- redhat/configs: NXP i.MX9 family (Steve Best)
- redhat/genlog.py: add support to list/process zstream Jira tickets (Herton R. Krzesinski)
- redhat: fix duplicate jira issues in the resolves line (Herton R. Krzesinski)
- redhat: add support for Jira issues in changelog (Herton R. Krzesinski)
- redhat/configs: turn on IMX8ULP CCM Clock Driver (Steve Best)
- redhat: update filter-modules fsdrvs list to reference smb instead of cifs (Patrick Talbert)
- Turn off some debug options found to impact performance (Justin M. Forbes)
- wifi: rtw89: enable RTL8852BE card in RHEL (Íñigo Huguet)
- redhat/configs: enable TEGRA186_GPC_DMA for RHEL (Mark Salter)
- Move imx8m configs from fedora to common (Mark Salter)
- redhat/configs: turn on lpuart serial port support Driver (Steve Best) [2208834]
- Turn off DEBUG_VM for non debug Fedora kernels (Justin M. Forbes)
- Enable CONFIG_BT on aarch64 (Charles Mirabile)
- redhat/configs: turn on CONFIG_MARVELL_CN10K_TAD_PMU (Michal Schmidt) [2042240]
- redhat/configs: Fix enabling MANA Infiniband (Kamal Heib)
- Fix file listing for symvers in uki (Justin M. Forbes)
- Fix up some Fedora config items (Justin M. Forbes)
- enable efifb for Nvidia (Justin M. Forbes)
- kernel.spec: package unstripped test_progs-no_alu32 (Felix Maurer)
- Turn on NFT_CONNLIMIT for Fedora (Justin M. Forbes)
- Include the information about builtin symbols into kernel-uki-virt package too (Vitaly Kuznetsov)
- redhat/configs: Fix incorrect configs location and content (Vladis Dronov)
- redhat/configs: turn on CONFIG_MARVELL_CN10K_DDR_PMU (Michal Schmidt) [2042241]
- redhat: configs: generic: x86: Disable CONFIG_VIDEO_OV2740 for x86 platform (Kate Hsuan)
- Enable IO_URING for RHEL (Justin M. Forbes)
- Turn on IO_URING for RHEL in pending (Justin M. Forbes)
- redhat: Remove editconfig (Prarit Bhargava)
- redhat: configs: fix CONFIG_WERROR replace in build_configs (Jan Stancek)
- redhat/configs: enable Maxim MAX77620 PMIC for RHEL (Mark Salter)
- kernel.spec: skip kernel meta package when building without up (Jan Stancek)
- redhat/configs: enable RDMA_RXE for RHEL (Kamal Heib) [2022578]
- redhat/configs: update RPCSEC_GSS_KRB5 configs (Scott Mayhew)
- redhat/Makefile: Support building linux-next (Thorsten Leemhuis)
- redhat/Makefile: support building stable-rc versions (Thorsten Leemhuis)
- redhat/Makefile: Add target to print DISTRELEASETAG (Thorsten Leemhuis)
- Remove EXPERT from ARCH_FORCE_MAX_ORDER for aarch64 (Justin M. Forbes)
- Revert "Merge branch 'unstripped-no_alu32' into 'os-build'" (Patrick Talbert)
- configs: Enable CONFIG_PAGE_POOL_STATS for common/generic (Patrick Talbert)
- redhat/configs: enable CONFIG_DELL_WMI_PRIVACY for both RHEL and Fedora (David Arcari)
- kernel.spec: package unstripped test_progs-no_alu32 (Felix Maurer)
- bpf/selftests: fix bpf selftests install (Jerome Marchand)
- kernel.spec: add bonding selftest (Hangbin Liu)
- Change FORCE_MAX_ORDER for ppc64 to be 8 (Justin M. Forbes)
- kernel.spec.template: Add global compression variables (Prarit Bhargava)
- kernel.spec.template: Use xz for KABI (Prarit Bhargava)
- kernel.spec.template: Remove gzip related aarch64 code (Prarit Bhargava)
- Add apple_bl to filter-modules (Justin M. Forbes)
- Add handshake-test to mod-intenal.list (Justin M. Forbes)
- Add regmap-kunit to mod-internal.list (Justin M. Forbes)
- configs: set CONFIG_PAGE_POOL_STATS (Patrick Talbert)
- Add apple_bl to fedora module_filter (Justin M. Forbes)
- Fix up some config mismatches in new Fedora config items (Justin M. Forbes)
- redhat/configs: disable CONFIG_USB_NET_SR9700 for aarch64 (Jose Ignacio Tornos Martinez)
- Reset changelog for 6.4 series (Justin M. Forbes)
- Reset RHEL_RELEASE for the 6.4 cycle (Justin M. Forbes)
- Fix up the RHEL configs for xtables and ipset (Justin M. Forbes)
- ark: enable wifi on aarch64 (Íñigo Huguet)
- fedora: wifi: hermes: disable 802.11b driver (Peter Robinson)
- fedora: wifi: libertas: use the LIBERTAS_THINFIRM driver (Peter Robinson)
- fedora: wifi: disable Zydas vendor (Peter Robinson)
- redhat: fix python ValueError in error path of merge.py (Clark Williams)
- fedora: arm: minor updates (Peter Robinson)
- kernel.spec: Fix UKI naming to comply with BLS (Philipp Rudo)
- redhat/kernel.spec.template: Suppress 'extracting debug info' noise in build log (Prarit Bhargava)
- Fedora 6.3 configs part 2 (Justin M. Forbes)
- redhat/configs: Enable CONFIG_X86_KERNEL_IBT for Fedora and ARK (Josh Poimboeuf)
- kernel.spec: gcov: make gcov subpackages per variant (Jan Stancek)
- kernel.spec: Gemini: add Epoch to perf and rtla subpackages (Jan Stancek)
- kernel.spec: Gemini: fix header provides for upgrade path (Jan Stancek)
- redhat: introduce Gemini versioning (Jan Stancek)
- redhat: separate RPM version from uname version (Jan Stancek)
- redhat: introduce GEMINI and RHEL_REBASE_NUM variable (Jan Stancek)
- ipmi: ssif_bmc: Add SSIF BMC driver (Tony Camuso)
- common: minor de-dupe of parallel port configs (Peter Robinson)
- Fedora 6.3 configs part 1 (Justin M. Forbes)
- redhat: configs: Enable CONFIG_MEMTEST to enable memory test (Kate Hsuan)
- Update Fedora arm filters after config updates (Nicolas Chauvet)
- redhat/kernel.spec.template: Fix kernel-tools-libs-devel dependency (Prarit Bhargava)
- redhat: fix the check for the n option (Patrick Talbert)
- common: de-dupe some options that are the same (Peter Robinson)
- generic: remove deleted options (Peter Robinson)
- redhat/configs: enable CONFIG_INTEL_TCC_COOLING for RHEL (David Arcari)
- Update Fedora ppc filters after config updates (Justin M. Forbes)
- Update Fedora aarch64 filters after config updates (Justin M. Forbes)
- fedora: arm: Updates for 6.3 (Peter Robinson)
- redhat: kunit: cleanup NITRO config and enable rescale test (Nico Pache)
- kernel.spec: use %%{package_name} to fix kernel-devel-matched Requires (Jan Stancek)
- kernel.spec: use %%{package_name} also for abi-stablelist subpackages (Jan Stancek)
- kernel.spec: use %%{package_name} also for tools subpackages (Jan Stancek)
- generic: common: Parport and paride/ata cleanups (Peter Robinson)
- CONFIG_SND_SOC_CS42L83 is no longer common (Justin M. Forbes)
- configs: arm: bring some configs in line with rhel configs in c9s (Mark Salter)
- arm64/configs: Put some arm64 configs in the right place (Mark Salter)
- cleanup removed R8188EU config (Peter Robinson)
- Make RHJOBS container friendly (Don Zickus)
- Remove scmversion from kernel.spec.template (Don Zickus)
- redhat/configs: Enable CONFIG_SND_SOC_CS42L83 (Neal Gompa)
- Use RHJOBS for create-tarball (Don Zickus)
- Enable CONFIG_NET_SCH_FQ_PIE for Fedora (Justin M. Forbes)
- Make Fedora debug configs more useful for debug (Justin M. Forbes)
- redhat/configs: enable Octeon TX2 network drivers for RHEL (Michal Schmidt) [2040643]
- redhat/kernel.spec.template: fix installonlypkg for meta package (Jan Stancek)
- redhat: version two of Makefile.rhelver tweaks (Clark Williams)
- redhat/configs: Disable CONFIG_GCC_PLUGINS (Prarit Bhargava)
- redhat/kernel.spec.template: Fix typo for process_configs.sh call (Neal Gompa)
- redhat/configs: CONFIG_CRYPTO_SM3_AVX_X86_64 is x86 only (Vladis Dronov)
- redhat/configs: Enable CONFIG_PINCTRL_METEORLAKE in RHEL (Prarit Bhargava)
- fedora: enable new image sensors (Peter Robinson)
- redhat/self-test: Update self-test data (Prarit Bhargava)
- redhat/kernel.spec.template: Fix hardcoded "kernel" (Prarit Bhargava)
- redhat/configs/generate_all_configs.sh: Fix config naming (Prarit Bhargava)
- redhat/kernel.spec.template: Pass SPECPACKAGE_NAME to generate_all_configs.sh (Prarit Bhargava)
- kernel.spec.template: Use SPECPACKAGE_NAME (Prarit Bhargava)
- redhat/Makefile: Copy spec file (Prarit Bhargava)
- redhat: Change PACKAGE_NAME to SPECPACKAGE_NAME (Prarit Bhargava)
- redhat/configs: Support the virtio_mmio.device parameter in Fedora (David Michael)
- Revert "Merge branch 'systemd-boot-unsigned' into 'os-build'" (Patrick Talbert)
- redhat/Makefile: fix default values for dist-brew's DISTRO and DIST (Íñigo Huguet)
- Remove cc lines from automatic configs (Don Zickus)
- Add rtla-hwnoise files (Justin M. Forbes)
- redhat/kernel.spec.template: Mark it as a non-executable file (Neal Gompa)
- fedora: arm: Enable DRM_PANEL_HIMAX_HX8394 (Javier Martinez Canillas)
- redhat/configs: CONFIG_HP_ILO location fix (Vladis Dronov)
- redhat: Fix build for kselftests mm (Nico Pache)
- fix tools build after vm to mm rename (Justin M. Forbes)
- redhat/spec: Update bpftool versioning scheme (Viktor Malik)
- redhat/configs: CONFIG_CRYPTO_SM4_AESNI_AVX*_X86_64 is x86 only (Prarit Bhargava)
- redhat:  adapt to upstream Makefile change (Clark Williams)
- redhat:  modify efiuki specfile changes to use variants convention (Clark Williams)
- Turn off DEBUG_INFO_COMPRESSED_ZLIB for Fedora (Justin M. Forbes)
- redhat/kernel.spec.template: Fix RHEL systemd-boot-unsigned dependency (Prarit Bhargava)
- Add hashtable_test to mod-internal.list (Justin M. Forbes)
- Add more kunit tests to mod-internal.list for 6.3 (Justin M. Forbes)
- Flip CONFIG_I2C_ALGOBIT to m (Justin M. Forbes)
- Flip I2C_ALGOBIT to m to avoid mismatch (Justin M. Forbes)
- kernel.spec: move modules.builtin to kernel-core (Jan Stancek)
- Turn on IDLE_INJECT for x86 (Justin M. Forbes)
- Flip CONFIG_IDLE_INJECT in pending (Justin M. Forbes)
- Trim Changelog for 6.3 series (Justin M. Forbes)
- Reset RHEL_RELEASE to 0 for the 6.3 cycle (Justin M. Forbes)
- redhat/configs: Enable CONFIG_V4L_TEST_DRIVERS related drivers (Enric Balletbo i Serra)
- redhat/configs: Enable UCSI_CCG support (David Marlin)
- Fix underline mark-up after text change (Justin M. Forbes)
- Turn on CONFIG_XFS_RT for Fedora (Justin M. Forbes)
- Consolidate common configs for 6.2 (Justin M. Forbes)
- aarch64: enable zboot (Gerd Hoffmann)
- redhat: remove duplicate pending-rhel config items (Patrick Talbert)
- Disable frame pointers (Justin M. Forbes)
- redhat/configs: update scripts and docs for ark -> rhel rename (Clark Williams)
- redhat/configs: rename ark configs dir to rhel (Clark Williams)
- Turn off CONFIG_DEBUG_INFO_COMPRESSED_ZLIB for ppc64le (Justin M. Forbes)
- kernel.spec: package unstripped kselftests/bpf/test_progs (Jan Stancek)
- kernel.spec: allow to package some binaries as unstripped (Jan Stancek)
- redhat/configs: Make merge.py portable for older python (Desnes Nunes)
- Fedora configs for 6.2 (Justin M. Forbes)
- redhat: Repair ELN build broken by the recent UKI changes (Vitaly Kuznetsov)
- redhat/configs: enable CONFIG_INET_DIAG_DESTROY (Andrea Claudi)
- Enable TDX Guest driver (Vitaly Kuznetsov)
- redhat/configs: Enable CONFIG_PCIE_PTM generically (Corinna Vinschen)
- redhat: Add sub-RPM with a EFI unified kernel image for virtual machines (Vitaly Kuznetsov)
- redhat/Makefile: Remove GIT deprecated message (Prarit Bhargava)
- Revert "redhat: configs: Disable xtables and ipset" (Phil Sutter)
- redhat/configs: Enable CONFIG_SENSORS_LM90 for RHEL (Mark Salter)
- Fix up SQUASHFS decompression configs (Justin M. Forbes)
- redhat/configs: enable CONFIG_OCTEON_EP as a module in ARK (Michal Schmidt) [2041990]
- redhat: ignore rpminspect runpath report on urandom_read selftest binaries (Herton R. Krzesinski)
- kernel.spec: add llvm-devel build requirement (Scott Weaver)
- Update self-test data to not expect debugbuildsenabled 0 (Justin M. Forbes)
- Turn off forced debug builds (Justin M. Forbes)
- Turn on debug builds for aarch64 Fedora (Justin M. Forbes)
- redhat/configs:  modify merge.py to match old overrides input (Clark Williams)
- redhat:  fixup pylint complaints (Clark Williams)
- redhat: remove merge.pl and references to it (Clark Williams)
- redhat: update merge.py to handle merge.pl corner cases (Clark Williams)
- Revert "redhat: fix elf got hardening for vm tools" (Don Zickus)
- Update rebase notes for Fedora (Justin M. Forbes)
- Update CONFIG_LOCKDEP_CHAINS_BITS to 19 (cmurf)
- redhat/configs: Turn on CONFIG_SPI_TEGRA210_QUAD for RHEL (Mark Salter)
- ark: aarch64: drop CONFIG_SMC911X (Peter Robinson)
- all: cleanup and de-dupe CDROM_PKTCDVD options. (Peter Robinson)
- all: remove CRYPTO_GF128MUL (Peter Robinson)
- all: cleanup UEFI options (Peter Robinson)
- common: arm64: Enable Ampere Altra SMpro Hardware Monitoring (Peter Robinson)
- fedora: enable STACKPROTECTOR_STRONG (Peter Robinson)
- fedora: enable STACKPROTECTOR on arm platforms (Peter Robinson)
- redhat/self-test: Update data with ENABLE_WERROR (Prarit Bhargava)
- redhat/Makefile.variables: Add ENABLE_WERROR (Prarit Bhargava)
- makefile: Add -Werror support for RHEL (Prarit Bhargava)
- redhat/Makefile.variables: Remove mention of Makefile.rhpkg (Prarit Bhargava)
- redhat/Makefile.variables: Alphabetize variables (Prarit Bhargava)
- gitlab-ci: use CI templates from production branch (Michael Hofmann)
- redhat/kernel.spec.template: Fix internal "File listed twice" errors (Prarit Bhargava)
- redhat: Remove stale .tmp_versions code and comments (Prarit Bhargava)
- redhat/kernel.spec.template: Fix vmlinux_decompressor on !s390x (Prarit Bhargava)
- redhat/kernel.spec.template: Remove unnecessary output from pathfix.py (Prarit Bhargava)
- Modularize CONFIG_ARM_CORESIGHT_PMU_ARCH_SYSTEM_PMU (Mark Salter)
- redhat/kernel.spec.template: Parallelize compression (Prarit Bhargava)
- config: Enable Security Path (Ricardo Robaina)
- redhat/self-test/data: Regenerate self-test data for make change (Prarit Bhargava)
- Update module filters for nvmem_u-boot-env (Justin M. Forbes)
- fedora: Updates for 6.2 merge (Peter Robinson)
- fedora: Updates for 6.1 merge (Peter Robinson)
- modules-core: use %%posttrans (Gerd Hoffmann)
- split sub-rpm kernel-modules-core from kernel-core (Gerd Hoffmann)
- Turn off CONFIG_MTK_T7XX for S390x (Justin M. Forbes)
- CI: add variable for variant handling (Veronika Kabatova)
- Fix up configs with SND_SOC_NAU8315 mismatch (Justin M. Forbes)
- CI: Do a full build for non-bot runs (Veronika Kabatova)
- Fix up configs with SND_SOC_NAU8315 mismatch (Justin M. Forbes)
- kernel/rh_messages.c: gcc12 warning on redundant NULL test (Eric Chanudet) [2142658]
- redhat/configs: Enable CRYPTO_CURVE25519 in ark (Prarit Bhargava)
- general: arm: cleanup ASPEED options (Peter Robinson)
- redhat/configs: ALSA - cleanups for the AMD Pink Sardine DMIC driver (Jaroslav Kysela)
- redhat/docs: Add FAQ entry for booting between Fedora & ELN/RHEL kernels (Prarit Bhargava)
- spec: add missing BuildRequires: python3-docutils for tools (Ondrej Mosnacek)
- config: enable RCU_TRACE for debug kernels (Wander Lairson Costa)
- Add siphash_kunit and strscpy_kunit to mod-internal.list (Justin M. Forbes)
- Add drm_kunit_helpers to mod-internal.list (Justin M. Forbes)
- Fix up configs for Fedora so we don't have a mismatch (Justin M. Forbes)
- Turn on CONFIG_SQUASHFS_DECOMP_SINGLE in pending (Justin M. Forbes)
- Trim changelog for 6.2 cycle (Justin M. Forbes)
- Reset RHEL_RELEASE for the 6.2 window. (Justin M. Forbes)
- redhat/kernel.spec.template: Fix cpupower file error (Prarit Bhargava)
- redhat/configs: aarhc64: clean up some erratum configs (Mark Salter)
- More Fedora configs for 6.1 as deps were switched on (Justin M. Forbes)
- redhat/configs: make SOC_TEGRA_CBB a module (Mark Salter)
- redhat/configs: aarch64: reorganize tegra configs to common dir (Mark Salter)
- Enforces buildroot if cross_arm (Nicolas Chauvet)
- Handle automated case when config generation works correctly (Don Zickus)
- Turn off CONFIG_CRYPTO_ARIA_AESNI_AVX_X86_64 (Justin M. Forbes)
- Turn off CONFIG_EFI_ZBOOT as it makes CKI choke (Justin M. Forbes)
- Fedora config updates for 6.1 (Justin M. Forbes)
- redhat: Remove cpupower files (Prarit Bhargava)
- redhat/configs: update CXL-related options to match what RHEL will use (John W. Linville)
- Clean up the config for the Tegra186 timer (Al Stone)
- redhat/configs: move CONFIG_TEGRA186_GPC_DMA config (Mark Salter)
- Check for kernel config git-push failures (Don Zickus)
- redhat: genlog.sh failures should interrupt the recipe (Patrick Talbert)
- Turn CONFIG_GNSS back on for Fedora (Justin M. Forbes)
- redhat/configs: enable CONFIG_GNSS for RHEL (Michal Schmidt)
- Turn off NVMEM_U_BOOT_ENV for fedora (Justin M. Forbes)
- Consolidate matching fedora and ark entries to common (Justin M. Forbes)
- Empty out redhat/configs/common (Justin M. Forbes)
- Adjust path to compressed vmlinux kernel image for s390x (Justin M. Forbes) [2149273]
- Fedora config updates for 6.1 (Justin M. Forbes)
- redhat: genlog.sh should expect genlog.py in the current directory (Patrick Talbert)
- redhat/configs: consolidate CONFIG_TEST_LIVEPATCH=m (Joe Lawrence)
- redhat/configs: enable CONFIG_TEST_LIVEPATCH=m for s390x (Julia Denham)
- Revert "Merge branch 'ark-make-help' into 'os-build'" (Scott Weaver)
- Remove recommendation to use 'common' for config changes. (Don Zickus)
- Update config to add i3c support for AArch64 (Mark Charlebois)
- redhat: Move cross-compile scripts into their own directory (Prarit Bhargava)
- redhat: Move yaml files into their own directory (Prarit Bhargava)
- redhat: Move update_scripts.sh into redhat/scripts (Prarit Bhargava)
- redhat: Move kernel-tools scripts into their own directory (Prarit Bhargava)
- redhat: Move gen-* scripts into their own directory (Prarit Bhargava)
- redhat: Move mod-* scripts into their own directory (Prarit Bhargava)
- redhat/Makefile: Fix RHJOBS grep warning (Prarit Bhargava)
- redhat: Force remove tmp file (Prarit Bhargava)
- redhat/configs: ALSA - cleanups for the CentOS 9.2 update (Jaroslav Kysela)
- CI: Use CKI container images from quay.io (Veronika Kabatova)
- redhat: clean up the partial-kgcov-snip.config file (Patrick Talbert)
- redhat: avoid picking up stray editor backups when processing configs (Clark Williams)
- CI: Remove old configs (Veronika Kabatova)
- redhat: override `make help` to include dist-help (Jonathan Toppins)
- redhat: make RHTEST stricter (Jonathan Toppins)
- redhat: Enable support for SN2201 system (Ivan Vecera)
- redhat/docs/index.rst: Add FLAVOR information to generate configs for local builds (Enric Balletbo i Serra)
- redhat: fix selftest git command so it picks the right commit (Patrick Talbert)
- redhat/configs: enable HP_WATCHDOG for aarch64 (Mark Salter)
- redhat: disable Kfence Kunit Test (Nico Pache)
- configs: enable CONFIG_LRU_GEN_ENABLED everywhere (Patrick Talbert)
- redhat: Enable WWAN feature and support for Intel, Qualcomm and Mediatek devices (Jose Ignacio Tornos Martinez)
- Turn on dln2 support (RHBZ 2110372) (Justin M. Forbes)
- Enable configs for imx8m PHYs (Al Stone)
- configs/fedora: Build some SC7180 clock controllers as modules (Javier Martinez Canillas)
- redhat/configs: Disable fbdev drivers and use simpledrm everywhere (Javier Martinez Canillas) [1986223]
- redhat: fix the branch we pull from the documentation tree (Herton R. Krzesinski)
- redhat/configs: change so watchdog is module versus builtin (Steve Best)
- redhat/configs: move CONFIG_ACPI_VIDEO to common/generic (Mark Langsdorf)
- enable imx8xm I2C configs properly (Al Stone)
- configs/fedora: Enable a few more drivers needed by the HP X2 Chromebook (Javier Martinez Canillas)
- enable the rtc-rv8803 driver on RHEL and Fedora (David Arcari)
- redhat/Makefile: Remove BUILD_SCRATCH_TARGET (Prarit Bhargava)
- configs: move CONFIG_INTEL_TDX_GUEST to common directory (Wander Lairson Costa)
- redhat/Makefile: Use new BUILD_TARGET for RHEL dist[g]-brew target (Prarit Bhargava)
- redhat: method.py: change the output loop to use 'values' method (Patrick Talbert)
- redhat: use 'update' method in merge.py (Patrick Talbert)
- redhat: Use a context manager in merge.py for opening the config file for reading (Patrick Talbert)
- redhat: automatically strip newlines in merge.py (Clark Williams)
- redhat: python replacement for merge.pl (Clark Williams)
- redhat/docs: Update with DISTLOCALVERSION (Prarit Bhargava)
- redhat/Makefile: Rename LOCALVERSION to DISTLOCALVERSION (Akihiko Odaki)
- Adjust FIPS module name in RHEL (Vladis Dronov)
- spec: prevent git apply from searching for the .git directory (Ondrej Mosnacek)
- redhat: Remove parallel_xz.sh (Prarit Bhargava)
- Turn on Multi-Gen LRU for Fedora (Justin M. Forbes)
- Add kasan_test to mod-internal.list (Justin M. Forbes)
- redhat/Makefile.variables: Fix typo with RHDISTGIT_TMP (Prarit Bhargava)
- spec: fix path to `installing_core` stamp file for subpackages (Jonathan Lebon)
- Remove unused ci scripts (Don Zickus)
- Rename rename FORCE_MAX_ZONEORDER to ARCH_FORCE_MAX_ORDER in configs (Justin M. Forbes)
- redhat: Add new fortify_kunit & is_signed_type_kunit to mod-internal.list (Patrick Talbert)
- Rename rename FORCE_MAX_ZONEORDER to ARCH_FORCE_MAX_ORDER in pending (Justin M. Forbes)
- Add acpi video to the filter_modules.sh for rhel (Justin M. Forbes)
- Change acpi_bus_get_acpi_device to acpi_get_acpi_dev (Justin M. Forbes)
- Turn on ACPI_VIDEO for arm (Justin M. Forbes)
- Turn on CONFIG_PRIME_NUMBERS as a module (Justin M. Forbes)
- Add new drm kunit tests to mod-internal.list (Justin M. Forbes)
- redhat: fix elf got hardening for vm tools (Frantisek Hrbata)
- kernel.spec.template: remove some temporary files early (Ondrej Mosnacek)
- kernel.spec.template: avoid keeping two copies of vmlinux (Ondrej Mosnacek)
- Add fortify_kunit to mod-internal.list (Justin M. Forbes)
- Add module filters for Fedora as acpi video has new deps (Justin M. Forbes)
- One more mismatch (Justin M. Forbes)
- Fix up pending for mismatches (Justin M. Forbes)
- Trim changelog with the reset (Justin M. Forbes)
- Reset the RHEL_RELEASE in Makefile.rhelver (Justin M. Forbes)
- Forgot too remove this from pending, it is set properly in ark (Justin M. Forbes)
- redhat/Makefile: Add DIST to git tags for RHEL (Prarit Bhargava)
- redhat/configs: Move CONFIG_ARM_SMMU_QCOM_DEBUG to common (Jerry Snitselaar)
- Common config cleanup for 6.0 (Justin M. Forbes)
- Allow selftests to fail without killing the build (Justin M. Forbes)
- redhat: Remove redhat/Makefile.rhpkg (Prarit Bhargava)
- redhat/Makefile: Move RHDISTGIT_CACHE and RHDISTGIT_TMP (Prarit Bhargava)
- redhat/Makefile.rhpkg: Remove RHDISTGIT_USER (Prarit Bhargava)
- redhat/Makefile: Move RHPKG_BIN to redhat/Makefile (Prarit Bhargava)
- common: clean up Android option with removal of CONFIG_ANDROID (Peter Robinson)
- redhat/configs: Remove x86_64 from priority files (Prarit Bhargava)
- redhat/configs/pending-ark: Remove x86_64 directory (Prarit Bhargava)
- redhat/configs/pending-fedora: Remove x86_64 directory (Prarit Bhargava)
- redhat/configs/fedora: Remove x86_64 directory (Prarit Bhargava)
- redhat/configs/common: Remove x86_64 directory (Prarit Bhargava)
- redhat/configs/ark: Remove x86_64 directory (Prarit Bhargava)
- redhat/configs/custom-overrides: Remove x86_64 directory (Prarit Bhargava)
- configs: use common CONFIG_ARM64_SME for ark and fedora (Mark Salter)
- redhat/configs: Add a warning message to priority.common (Prarit Bhargava)
- redhat/configs: Enable INIT_STACK_ALL_ZERO for Fedora (Miko Larsson)
- redhat: Set CONFIG_MAXLINEAR_GPHY to =m (Petr Oros)
- redhat/configs enable CONFIG_INTEL_IFS (David Arcari)
- redhat: Remove filter-i686.sh.rhel (Prarit Bhargava)
- redhat/Makefile: Set PATCHLIST_URL to none for RHEL/cs9 (Prarit Bhargava)
- redhat: remove GL_DISTGIT_USER, RHDISTGIT and unify dist-git cloning (Prarit Bhargava)
- redhat/Makefile.variables: Add ADD_COMMITID_TO_VERSION (Prarit Bhargava)
- kernel.spec: disable vmlinux.h generation for s390 zfcpdump config (Prarit Bhargava)
- perf: Require libbpf 0.6.0 or newer (Prarit Bhargava)
- kabi: add stablelist helpers (Prarit Bhargava)
- Makefile: add kabi targets (Prarit Bhargava)
- kabi: add support for symbol namespaces into check-kabi (Prarit Bhargava)
- kabi: ignore new stablelist metadata in show-kabi (Prarit Bhargava)
- redhat/Makefile: add dist-assert-tree-clean target (Prarit Bhargava)
- redhat/kernel.spec.template: Specify vmlinux.h path when building samples/bpf (Prarit Bhargava) [2041365]
- spec: Fix separate tools build (Prarit Bhargava) [2054579]
- redhat/scripts: Update merge-subtrees.sh with new subtree location (Prarit Bhargava)
- redhat/kernel.spec.template: enable dependencies generation (Prarit Bhargava)
- redhat: build and include memfd to kernel-selftests-internal (Prarit Bhargava) [2027506]
- redhat/kernel.spec.template: Link perf with --export-dynamic (Prarit Bhargava)
- redhat: kernel.spec: selftests: abort on build failure (Prarit Bhargava)
- redhat: configs: move CONFIG_SERIAL_MULTI_INSTANTIATE=m settings to common/x86 (Jaroslav Kysela)
- configs: enable CONFIG_HP_ILO for aarch64 (Mark Salter)
- all: cleanup dell config options (Peter Robinson)
- redhat: Include more kunit tests (Nico Pache)
- common: some minor cleanups/de-dupe (Peter Robinson)
- common: enable INTEGRITY_MACHINE_KEYRING on all configuraitons (Peter Robinson)
- Fedora 6.0 configs update (Justin M. Forbes)
- redhat/self-test: Ignore .rhpkg.mk files (Prarit Bhargava)
- redhat/configs: Enable CONFIG_PRINTK_INDEX on Fedora (Prarit Bhargava)
- redhat/configs: Cleanup CONFIG_X86_KERNEL_IBT (Prarit Bhargava)
- Fix up SND_CTL debug options (Justin M. Forbes)
- redhat: create /boot symvers link if it doesn't exist (Jan Stancek)
- redhat: remove duplicate kunit tests in mod-internal.list (Nico Pache)
- configs/fedora: Make Fedora work with HNS3 network adapter (Zamir SUN)
- redhat/configs/fedora/generic: Enable CONFIG_BLK_DEV_UBLK on Fedora (Richard W.M. Jones) [2122595]
- fedora: disable IWLMEI (Peter Robinson)
- redhat/configs: enable UINPUT on aarch64 (Benjamin Tissoires)
- Fedora 6.0 configs part 1 (Justin M. Forbes)
- redhat/Makefile: Always set UPSTREAM (Prarit Bhargava)
- redhat/configs: aarch64: Turn on Apple Silicon configs for Fedora (Eric Curtin)
- Add cpumask_kunit to mod-internal.list (Justin M. Forbes)
- config - consolidate disabled MARCH options on s390x (Dan Horák)
- move the baseline arch to z13 for s390x in F-37+ (Dan Horák)
- redhat/scripts/rh-dist-git.sh: Fix outdated cvs reference (Prarit Bhargava)
- redhat/scripts/expand_srpm.sh: Use Makefile variables (Prarit Bhargava)
- redhat/scripts/clone_tree.sh: Use Makefile variables (Prarit Bhargava)
- Fedora: arm changes for 6.0, part 1, with some ACPI (Peter Robinson)
- redhat/self-test: Fix shellcheck errors (Prarit Bhargava)
- redhat/docs: Add dist-brew BUILD_FLAGS information (Prarit Bhargava)
- redhat: change the changelog item for upstream merges (Herton R. Krzesinski)
- redhat: fix dist-release build number test (Herton R. Krzesinski)
- redhat: fix release number bump when dist-release-changed runs (Herton R. Krzesinski)
- redhat: use new genlog.sh script to detect changes for dist-release (Herton R. Krzesinski)
- redhat: move changelog addition to the spec file back into genspec.sh (Herton R. Krzesinski)
- redhat: always add a rebase entry when ark merges from upstream (Herton R. Krzesinski)
- redhat: drop merge ark patches hack (Herton R. Krzesinski)
- redhat: don't hardcode temporary changelog file (Herton R. Krzesinski)
- redhat: split changelog generation from genspec.sh (Herton R. Krzesinski)
- redhat: configs: Disable FIE on arm (Jeremy Linton) [2012226]
- redhat/Makefile: Clean linux tarballs (Prarit Bhargava)
- redhat/configs: Cleanup CONFIG_ACPI_AGDI (Prarit Bhargava)
- spec: add cpupower daemon reload on install/upgrade (Jarod Wilson)
- redhat: properly handle binary files in patches (Ondrej Mosnacek)
- Add python3-setuptools buildreq for perf (Justin M. Forbes)
- Add cros_kunit to mod-internal.list (Justin M. Forbes)
- Add new tests to mod-internal.list (Justin M. Forbes)
- Turn off some Kunit tests in pending (Justin M. Forbes)
- Clean up a mismatch in Fedora configs (Justin M. Forbes)
- redhat/configs: Sync up Retbleed configs with centos-stream (Waiman Long)
- Change CRYPTO_BLAKE2S_X86 from m to y (Justin M. Forbes)
- Leave CONFIG_ACPI_VIDEO on for x86 only (Justin M. Forbes)
- Fix BLAKE2S_ARM and BLAKE2S_X86 configs in pending (Justin M. Forbes)
- Fix pending for ACPI_VIDEO (Justin M. Forbes)
- Reset release (Justin M. Forbes)
- redhat/configs: Fix rm warning on config warnings (Eric Chanudet)
- redhat/Makefile: Deprecate PREBUILD_GIT_ONLY variable (Prarit Bhargava)
- redhat/Makefile: Deprecate SINGLE_TARBALL variable (Prarit Bhargava)
- redhat/Makefile: Deprecate GIT variable (Prarit Bhargava)
- Update CONFIG_LOCKDEP_CHAINS_BITS to 18 (cmurf)
- Add new FIPS module name and version configs (Vladis Dronov)
- redhat/configs/fedora: Make PowerPC's nx-gzip buildin (Jakub Čajka)
- omit unused Provides (Dan Horák)
- self-test: Add test for DIST=".eln" (Prarit Bhargava)
- redhat: Enable CONFIG_LZ4_COMPRESS on Fedora (Prarit Bhargava)
- fedora: armv7: enable MMC_STM32_SDMMC (Peter Robinson)
- .gitlab-ci.yaml: Add test for dist-get-buildreqs target (Prarit Bhargava)
- redhat/docs: Add information on build dependencies (Prarit Bhargava)
- redhat/Makefile: Add better pass message for dist-get-buildreqs (Prarit Bhargava)
- redhat/Makefile: Provide a better message for system-sb-certs (Prarit Bhargava)
- redhat/Makefile: Change dist-buildreq-check to a non-blocking target (Prarit Bhargava)
- create-data: Parallelize spec file data (Prarit Bhargava)
- create-data.sh: Store SOURCES Makefile variable (Prarit Bhargava)
- redhat/Makefile: Split up setup-source target (Prarit Bhargava)
- create-data.sh: Redefine varfilename (Prarit Bhargava)
- create-data.sh: Parallelize variable file creation (Prarit Bhargava)
- redhat/configs: Enable CONFIG_LZ4_COMPRESS (Prarit Bhargava)
- redhat/docs: Update brew information (Prarit Bhargava)
- redhat/Makefile: Fix eln BUILD_TARGET (Prarit Bhargava)
- redhat/Makefile: Set BUILD_TARGET for dist-brew (Prarit Bhargava)
- kernel.spec.template: update (s390x) expoline.o path (Joe Lawrence)
- fedora: enable BCM_NET_PHYPTP (Peter Robinson)
- Fedora 5.19 configs update part 2 (Justin M. Forbes)
- redhat/Makefile: Change fedora BUILD_TARGET (Prarit Bhargava)
- New configs in security/keys (Fedora Kernel Team)
- Fedora: arm: enable a pair of drivers (Peter Robinson)
- redhat: make kernel-zfcpdump-core to not provide kernel-core/kernel (Herton R. Krzesinski)
- redhat/configs: Enable QAT devices for arches other than x86 (Vladis Dronov)
- Fedora 5.19 configs pt 1 (Justin M. Forbes)
- redhat: Exclude cpufreq.h from kernel-headers (Patrick Talbert)
- Add rtla subpackage for kernel-tools (Justin M. Forbes)
- fedora: arm: enable a couple of QCom drivers (Peter Robinson)
- redhat/Makefile: Deprecate BUILD_SCRATCH_TARGET (Prarit Bhargava)
- redhat: enable CONFIG_DEVTMPFS_SAFE (Mark Langsdorf)
- redhat/Makefile: Remove deprecated variables and targets (Prarit Bhargava)
- Split partner modules into a sub-package (Alice Mitchell)
- Enable kAFS and it's dependancies in RHEL (Alice Mitchell)
- Enable Marvell OcteonTX2 crypto device in ARK (Vladis Dronov)
- redhat/Makefile: Remove --scratch from BUILD_TARGET (Prarit Bhargava)
- redhat/Makefile: Fix dist-brew and distg-brew targets (Prarit Bhargava)
- fedora: arm64: Initial support for TI Keystone 3 (ARCH_K3) (Peter Robinson)
- fedora: arm: enable Hardware Timestamping Engine support (Peter Robinson)
- fedora: wireless: disable SiLabs and PureLiFi (Peter Robinson)
- fedora: updates for 5.19 (Peter Robinson)
- fedora: minor updates for Fedora configs (Peter Robinson)
- configs/fedora: Enable the pinctrl SC7180 driver built-in (Enric Balletbo i Serra)
- redhat/configs: enable CONFIG_DEBUG_NET for debug kernel (Hangbin Liu)
- redhat/Makefile: Add SPECKABIVERSION variable (Prarit Bhargava)
- redhat/self-test: Provide better failure output (Prarit Bhargava)
- redhat/self-test: Reformat tests to kernel standard (Prarit Bhargava)
- redhat/self-test: Add purpose and header to each test (Prarit Bhargava)
- Drop outdated CRYPTO_ECDH configs (Vladis Dronov)
- Brush up crypto SHA512 and USER configs (Vladis Dronov)
- Brush up crypto ECDH and ECDSA configs (Vladis Dronov)
- redhat/self-test: Update data set (Prarit Bhargava)
- create-data.sh: Reduce specfile data output (Prarit Bhargava)
- redhat/configs: restore/fix core INTEL_LPSS configs to be builtin again (Hans de Goede)
- Enable CKI on os-build MRs only (Don Zickus)
- self-test: Fixup Makefile contents test (Prarit Bhargava)
- redhat/self-test: self-test data update (Prarit Bhargava)
- redhat/self-test: Fix up create-data.sh to not report local variables (Prarit Bhargava)
- redhat/configs/fedora: Enable a set of modules used on some x86 tablets (Hans de Goede)
- redhat/configs: Make INTEL_SOC_PMIC_CHTDC_TI builtin (Hans de Goede)
- redhat/configs/fedora: enable missing modules modules for Intel IPU3 camera support (Hans de Goede)
- Common: minor cleanups (Peter Robinson)
- fedora: some minor Fedora cleanups (Peter Robinson)
- fedora: drop X86_PLATFORM_DRIVERS_DELL dupe (Peter Robinson)
- redhat: change tools_make macro to avoid full override of variables in Makefile (Herton R. Krzesinski)
- Fix typo in Makefile for Fedora Stable Versioning (Justin M. Forbes)
- Remove duplicates from ark/generic/s390x/zfcpdump/ (Vladis Dronov)
- Move common/debug/s390x/zfcpdump/ configs to ark/debug/s390x/zfcpdump/ (Vladis Dronov)
- Move common/generic/s390x/zfcpdump/ configs to ark/generic/s390x/zfcpdump/ (Vladis Dronov)
- Drop RCU_EXP_CPU_STALL_TIMEOUT to 0, we are not really android (Justin M. Forbes)
- redhat/configs/README: Update the README (Prarit Bhargava)
- redhat/docs: fix hyperlink typo (Patrick Talbert)
- all: net: remove old NIC/ATM drivers that use virt_to_bus() (Peter Robinson)
- Explicitly turn off CONFIG_KASAN_INLINE for ppc (Justin M. Forbes)
- redhat/docs: Add a description of kernel naming (Prarit Bhargava)
- Change CRYPTO_CHACHA_S390 from m to y (Justin M. Forbes)
- enable CONFIG_NET_ACT_CTINFO in ark (Davide Caratti)
- redhat/configs: enable CONFIG_SP5100_TCO (David Arcari)
- redhat/configs: Set CONFIG_VIRTIO_IOMMU on x86_64 (Eric Auger) [2089765]
- Turn off KASAN_INLINE for RHEL ppc in pending (Justin M. Forbes)
- redhat/kernel.spec.template: update selftest data via "make dist-self-test-data" (Denys Vlasenko)
- redhat/kernel.spec.template: remove stray *.hardlink-temporary files, if any (Denys Vlasenko)
- Fix up ZSMALLOC config for s390 (Justin M. Forbes)
- Turn on KASAN_OUTLINE for ppc debug (Justin M. Forbes)
- Turn on KASAN_OUTLINE for PPC debug to avoid mismatch (Justin M. Forbes)
- Fix up crypto config mistmatches (Justin M. Forbes)
- Fix up config mismatches (Justin M. Forbes)
- generic/fedora: cleanup and disable Lightning Moutain SoC (Peter Robinson)
- redhat: Set SND_SOC_SOF_HDA_PROBES to =m (Patrick Talbert)
- Fix versioning on stable Fedora (Justin M. Forbes)
- Enable PAGE_POOL_STATS for arm only (Justin M. Forbes)
- Revert "Merge branch 'fix-ci-20220523' into 'os-build'" (Patrick Talbert)
- Fix changelog one more time post rebase (Justin M. Forbes)
- Flip CONFIG_RADIO_ADAPTERS to module for Fedora (Justin M. Forbes)
- Reset Release for 5.19 (Justin M. Forbes)
- redhat/Makefile: Drop quotation marks around string definitions (Prarit Bhargava)
- Fedora: arm: Updates for QCom devices (Peter Robinson)
- Fedora arm and generic updates for 5.17 (Peter Robinson)
- enable COMMON_CLK_SI5341 for Xilinx ZYNQ-MP (Peter Robinson)
- Turn on CONFIG_DM_VERITY_VERIFY_ROOTHASH_SIG_SECONDARY_KEYRING for Fedora (Justin M. Forbes)
- redhat/self-test/data: Update data set (Prarit Bhargava)
- Revert variable switch for lasttag (Justin M. Forbes)
- redhat: Add self-tests to .gitlab-ci.yml (Prarit Bhargava)
- redhat/self-test: Update data (Prarit Bhargava)
- redhat/self-test: Unset Makefile variables (Prarit Bhargava)
- redhat/self-test: Omit SHELL variable from test data (Prarit Bhargava)
- Add CONFIG_EFI_DXE_MEM_ATTRIBUTES (Justin M. Forbes)
- Update filter-modules for mlx5-vfio-pci (Justin M. Forbes)
- Fedora configs for 5.18 (Justin M. Forbes)
- self-test/data/create-data.sh: Avoid SINGLE_TARBALL warning (Prarit Bhargava)
- redhat/Makefile: Rename PREBUILD to UPSTREAMBUILD (Prarit Bhargava)
- redhat/Makefile: Rename BUILDID to LOCALVERSION (Prarit Bhargava)
- redhat/Makefile: Fix dist-brew & distg-brew targets (Prarit Bhargava)
- redhat/Makefile: Reorganize MARKER code (Prarit Bhargava)
- redhat/scripts/new_release.sh: Use Makefile variables (Prarit Bhargava)
- redhat/Makefile: Rename __YSTREAM and __ZSTREAM (Prarit Bhargava)
- redhat/genspec.sh: Add comment about SPECBUILDID variable (Prarit Bhargava)
- redhat/kernel.spec.template: Move genspec variables into one section (Prarit Bhargava)
- redhat/kernel.spec.template: Remove kversion (Prarit Bhargava)
- redhat/Makefile: Add SPECTARFILE_RELEASE comment (Prarit Bhargava)
- redhat/Makefile: Rename RPMVERSION to BASEVERSION (Prarit Bhargava)
- redhat/Makefile: Target whitespace cleanup (Prarit Bhargava)
- redhat/Makefile: Move SPECRELEASE to genspec.sh (Prarit Bhargava)
- redhat/Makefile: Add kernel-NVR comment (Prarit Bhargava)
- redhat/Makefile: Use SPECFILE variable (Prarit Bhargava)
- redhat/Makefile: Remove KEXTRAVERSION (Prarit Bhargava)
- redhat: Enable VM kselftests (Nico Pache) [1978539]
- redhat: enable CONFIG_TEST_VMALLOC for vm selftests (Nico Pache)
- redhat: Enable HMM test to be used by the kselftest test suite (Nico Pache)
- redhat/Makefile.variables: Change git hash length to default (Prarit Bhargava)
- redhat/Makefile: Drop quotation marks around string definitions (Prarit Bhargava)
- Turn on INTEGRITY_MACHINE_KEYRING for Fedora (Justin M. Forbes)
- redhat/configs: fix CONFIG_INTEL_ISHTP_ECLITE (David Arcari)
- redhat/configs: Fix rm warning on error (Prarit Bhargava)
- Fix nightly merge CI (Don Zickus)
- redhat/kernel.spec.template: fix standalone tools build (Jan Stancek)
- Add system-sb-certs for RHEL-9 (Don Zickus)
- Fix dist-buildcheck-reqs (Don Zickus)
- move DAMON configs to correct directory (Chris von Recklinghausen)
- redhat: indicate HEAD state in tarball/rpm name (Jarod Wilson)
- Fedora 5.18 config set part 1 (Justin M. Forbes)
- fedora: arm: Enable new Rockchip 356x series drivers (Peter Robinson)
- fedora: arm: enable DRM_I2C_NXP_TDA998X on aarch64 (Peter Robinson)
- redhat/self-test: Add test to verify Makefile declarations. (Prarit Bhargava)
- redhat/Makefile: Add RHTEST (Prarit Bhargava)
- redhat: shellcheck cleanup (Prarit Bhargava)
- redhat/self-test/data: Cleanup data (Prarit Bhargava)
- redhat/self-test: Add test to verify SPEC variables (Prarit Bhargava)
- redhat/Makefile: Add 'duplicate' SPEC entries for user set variables (Prarit Bhargava)
- redhat/Makefile: Rename TARFILE_RELEASE to SPECTARFILE_RELEASE (Prarit Bhargava)
- redhat/genspec: Rename PATCHLIST_CHANGELOG to SPECPATCHLIST_CHANGELOG (Prarit Bhargava)
- redhat/genspec: Rename DEBUG_BUILDS_ENABLED to SPECDEBUG_BUILDS_ENABLED (Prarit Bhargava)
- redhat/Makefile: Rename PKGRELEASE to SPECBUILD (Prarit Bhargava)
- redhat/genspec: Rename BUILDID_DEFINE to SPECBUILDID (Prarit Bhargava)
- redhat/Makefile: Rename CHANGELOG to SPECCHANGELOG (Prarit Bhargava)
- redhat/Makefile: Rename RPMKEXTRAVERSION to SPECKEXTRAVERSION (Prarit Bhargava)
- redhat/Makefile: Rename RPMKSUBLEVEL to SPECKSUBLEVEL (Prarit Bhargava)
- redhat/Makefile: Rename RPMKPATCHLEVEL to SPECKPATCHLEVEL (Prarit Bhargava)
- redhat/Makefile: Rename RPMKVERSION to SPECKVERSION (Prarit Bhargava)
- redhat/Makefile: Rename KVERSION to SPECVERSION (Prarit Bhargava)
- redhat/Makefile: Deprecate some simple targets (Prarit Bhargava)
- redhat/Makefile: Use KVERSION (Prarit Bhargava)
- redhat/configs: Set GUP_TEST in debug kernel (Joel Savitz)
- enable DAMON configs (Chris von Recklinghausen) [2004233]
- redhat: add zstream switch for zstream release numbering (Herton R. Krzesinski)
- redhat: change kabi tarballs to use the package release (Herton R. Krzesinski)
- redhat: generate distgit changelog in genspec.sh as well (Herton R. Krzesinski)
- redhat: make genspec prefer metadata from git notes (Herton R. Krzesinski)
- redhat: use tags from git notes for zstream to generate changelog (Herton R. Krzesinski)
- ARK: Remove code marking drivers as tech preview (Peter Georg)
- ARK: Remove code marking devices deprecated (Peter Georg)
- ARK: Remove code marking devices unmaintained (Peter Georg)
- rh_message: Fix function name (Peter Georg) [2019377]
- Turn on CONFIG_RANDOM_TRUST_BOOTLOADER (Justin M. Forbes)
- redhat/configs: aarch64: enable CPU_FREQ_GOV_SCHEDUTIL (Mark Salter)
- Move CONFIG_HW_RANDOM_CN10K to a proper place (Vladis Dronov)
- redhat/self-test: Clean up data set (Prarit Bhargava)
- redhat/Makefile.rhpkg: Remove quotes for RHDISTGIT (Prarit Bhargava)
- redhat/scripts/create-tarball.sh: Use Makefile variables (Prarit Bhargava)
- redhat/Makefile: Deprecate SINGLE_TARBALL (Prarit Bhargava)
- redhat/Makefile: Move SINGLE_TARBALL to Makefile.variables (Prarit Bhargava)
- redhat/Makefile: Use RPMVERSION (Prarit Bhargava)
- redhat/scripts/rh-dist-git.sh: Use Makefile variables (Prarit Bhargava)
- redhat/configs/build_configs.sh: Use Makefile variables (Prarit Bhargava)
- redhat/configs/process_configs.sh: Use Makefile variables (Prarit Bhargava)
- redhat/kernel.spec.template: Use RPM_BUILD_NCPUS (Prarit Bhargava)
- redhat/configs/generate_all_configs.sh: Use Makefile variables (Prarit Bhargava)
- redhat/configs: enable nf_tables SYNPROXY extension on ark (Davide Caratti)
- fedora: Disable fbdev drivers missed before (Javier Martinez Canillas)
- Redhat: enable Kfence on production servers (Nico Pache)
- redhat: ignore known empty patches on the patches rpminspect test (Herton R. Krzesinski)
- kernel-ark: arch_hw Update CONFIG_MOUSE_VSXXXAA=m (Tony Camuso) [2062909]
- spec: keep .BTF section in modules for s390 (Yauheni Kaliuta) [2071969]
- kernel.spec.template: Ship arch/s390/lib/expoline.o in kernel-devel (Ondrej Mosnacek)
- redhat: disable tv/radio media device infrastructure (Jarod Wilson)
- redhat/configs: clean up INTEL_LPSS configuration (David Arcari)
- Have to rename the actual contents too (Justin M. Forbes)
- The CONFIG_SATA_MOBILE_LPM_POLICY rebane was reverted (Justin M. Forbes)
- redhat: Enable KASAN on all ELN debug kernels (Nico Pache)
- redhat: configs: Enable INTEL_IOMMU_DEBUGFS for debug builds (Jerry Snitselaar)
- generic: can: disable CAN_SOFTING everywhere (Peter Robinson)
- redhat/configs: Enable CONFIG_DM_ERA=m for all (Yanko Kaneti)
- redhat/configs: enable CONFIG_SAMPLE_VFIO_MDEV_MTTY (Patrick Talbert)
- Build intel_sdsi with %%{tools_make} (Justin M. Forbes)
- configs: remove redundant Fedora config for INTEL_IDXD_COMPAT (Jerry Snitselaar)
- redhat/configs: enable CONFIG_RANDOMIZE_KSTACK_OFFSET_DEFAULT (Joel Savitz) [2026319]
- configs: enable CONFIG_RMI4_F3A (Benjamin Tissoires)
- redhat: configs: Disable TPM 1.2 specific drivers (Jerry Snitselaar)
- redhat/configs: Enable cr50 I2C TPM interface (Akihiko Odaki)
- spec: make HMAC file encode relative path (Jonathan Lebon)
- redhat/kernel.spec.template: Add intel_sdsi utility (Prarit Bhargava)
- Spec fixes for intel-speed-select (Justin M. Forbes)
- Add Partner Supported taint flag to kAFS (Alice Mitchell) [2038999]
- Add Partner Supported taint flag (Alice Mitchell) [2038999]
- Enabled INTEGRITY_MACHINE_KEYRING for all configs. (Peter Robinson)
- redhat/configs: Enable CONFIG_RCU_SCALE_TEST & CONFIG_RCU_REF_SCALE_TEST (Waiman Long)
- Add clk_test and clk-gate_test to mod-internal.list (Justin M. Forbes)
- redhat/self-tests: Ignore UPSTREAM (Prarit Bhargava)
- redhat/self-tests: Ignore RHGITURL (Prarit Bhargava)
- redhat/Makefile.variables: Extend git hash length to 15 (Prarit Bhargava)
- redhat/self-test: Remove changelog from spec files (Prarit Bhargava)
- redhat/genspec.sh: Rearrange genspec.sh (Prarit Bhargava)
- redhat/self-test: Add spec file data (Prarit Bhargava)
- redhat/self-test: Add better dist-dump-variables test (Prarit Bhargava)
- redhat/self-test: Add variable test data (Prarit Bhargava)
- redhat/config: Remove obsolete CONFIG_MFD_INTEL_PMT (David Arcari)
- redhat/configs: enable CONFIG_INTEL_ISHTP_ECLITE (David Arcari)
- Avoid creating files in $RPM_SOURCE_DIR (Nicolas Chauvet)
- Flip CRC64 from off to y (Justin M. Forbes)
- New configs in lib/Kconfig (Fedora Kernel Team)
- disable redundant assignment of CONFIG_BQL on ARK (Davide Caratti)
- redhat/configs: remove unnecessary GPIO options for aarch64 (Brian Masney)
- redhat/configs: remove viperboard related Kconfig options (Brian Masney)
- redhat/configs/process_configs.sh: Avoid race with find (Prarit Bhargava)
- redhat/configs/process_configs.sh: Remove CONTINUEONERROR (Prarit Bhargava)
- Remove i686 configs and filters (Justin M. Forbes)
- redhat/configs: Set CONFIG_X86_AMD_PSTATE built-in on Fedora (Prarit Bhargava)
- Fix up mismatch with CRC64 (Justin M. Forbes)
- Fedora config updates to fix process_configs (Justin M. Forbes)
- redhat: Fix release tagging (Prarit Bhargava)
- redhat/self-test: Fix version tag test (Prarit Bhargava)
- redhat/self-test: Fix BUILD verification test (Prarit Bhargava)
- redhat/self-test: Cleanup SRPM related self-tests (Prarit Bhargava)
- redhat/self-test: Fix shellcheck test (Prarit Bhargava)
- redhat/configs: Disable watchdog components (Prarit Bhargava)
- redhat/README.Makefile: Add a Makefile README file (Prarit Bhargava)
- redhat/Makefile: Remove duplicated code (Prarit Bhargava)
- Add BuildRequires libnl3-devel for intel-speed-select (Justin M. Forbes)
- Add new kunit tests for 5.18 to mod-internal.list (Justin M. Forbes)
- Fix RHDISTGIT for Fedora (Justin M. Forbes)
- redhat/configs/process_configs.sh: Fix race with tools generation (Prarit Bhargava)
- New configs in drivers/dax (Fedora Kernel Team)
- Fix up CONFIG_SND_AMD_ACP_CONFIG files (Patrick Talbert)
- Remove CONFIG_SND_SOC_SOF_DEBUG_PROBES files (Patrick Talbert)
- SATA_MOBILE_LPM_POLICY is now SATA_LPM_POLICY (Justin M. Forbes)
- Define SNAPSHOT correctly when VERSION_ON_UPSTREAM is 0 (Justin M. Forbes)
- redhat/Makefile: Fix dist-git (Prarit Bhargava)
- Clean up the changelog (Justin M. Forbes)
- Change the pending-ark CONFIG_DAX to y due to mismatch (Justin M. Forbes)
- Reset Makefile.rhelver for the 5.18 cycle (Justin M. Forbes)
- Enable net reference count trackers in all debug kernels (Jiri Benc)
- redhat/Makefile: Reorganize variables (Prarit Bhargava)
- redhat/Makefile: Add some descriptions (Prarit Bhargava)
- redhat/Makefile: Move SNAPSHOT check (Prarit Bhargava)
- redhat/Makefile: Deprecate BREW_FLAGS, KOJI_FLAGS, and TEST_FLAGS (Prarit Bhargava)
- redhat/genspec.sh: Rework RPMVERSION variable (Prarit Bhargava)
- redhat/Makefile: Remove dead comment (Prarit Bhargava)
- redhat/Makefile: Cleanup KABI* variables. (Prarit Bhargava)
- redhat/Makefile.variables: Default RHGITCOMMIT to HEAD (Prarit Bhargava)
- redhat/scripts/create-tarball.sh: Use Makefile TARBALL variable (Prarit Bhargava)
- redhat/Makefile: Remove extra DIST_BRANCH (Prarit Bhargava)
- redhat/Makefile: Remove STAMP_VERSION (Prarit Bhargava)
- redhat/Makefile: Move NO_CONFIGCHECKS to Makefile.variables (Prarit Bhargava)
- redhat/Makefile: Move RHJOBS to Makefile.variables (Prarit Bhargava)
- redhat/Makefile: Move RHGIT* variables to Makefile.variables (Prarit Bhargava)
- redhat/Makefile: Move PREBUILD_GIT_ONLY to Makefile.variables (Prarit Bhargava)
- redhat/Makefile: Move BUILD to Makefile.variables (Prarit Bhargava)
- redhat/Makefile: Move BUILD_FLAGS to Makefile.variables. (Prarit Bhargava)
- redhat/Makefile: Move BUILD_PROFILE to Makefile.variables (Prarit Bhargava)
- redhat/Makefile: Move BUILD_TARGET and BUILD_SCRATCH_TARGET to Makefile.variables (Prarit Bhargava)
- redhat/Makefile: Remove RHPRODUCT variable (Prarit Bhargava)
- redhat/Makefile: Cleanup DISTRO variable (Prarit Bhargava)
- redhat/Makefile: Move HEAD to Makefile.variables. (Prarit Bhargava)
- redhat: Combine Makefile and Makefile.common (Prarit Bhargava)
- redhat/koji/Makefile: Decouple koji Makefile from Makefile.common (Prarit Bhargava)
- Set CONFIG_SND_SOC_SOF_MT8195 for Fedora and turn on VDPA_SIM_BLOCK (Justin M. Forbes)
- Add asus_wmi_sensors modules to filters for Fedora (Justin M. Forbes)
- redhat: spec: trigger dracut when modules are installed separately (Jan Stancek)
- Last of the Fedora 5.17 configs initial pass (Justin M. Forbes)
- redhat/Makefile: Silence dist-clean-configs output (Prarit Bhargava)
- Fedora 5.17 config updates (Justin M. Forbes)
- Setting CONFIG_I2C_SMBUS to "m" for ark (Gopal Tiwari)
- Print arch with process_configs errors (Justin M. Forbes)
- Pass RHJOBS to process_configs for dist-configs-check as well (Justin M. Forbes)
- redhat/configs/process_configs.sh: Fix issue with old error files (Prarit Bhargava)
- redhat/configs/build_configs.sh: Parallelize execution (Prarit Bhargava)
- redhat/configs/build_configs.sh: Provide better messages (Prarit Bhargava)
- redhat/configs/build_configs.sh: Create unique output files (Prarit Bhargava)
- redhat/configs/build_configs.sh: Add local variables (Prarit Bhargava)
- redhat/configs/process_configs.sh: Parallelize execution (Prarit Bhargava)
- redhat/configs/process_configs.sh: Provide better messages (Prarit Bhargava)
- redhat/configs/process_configs.sh: Create unique output files (Prarit Bhargava)
- redhat/configs/process_configs.sh: Add processing config function (Prarit Bhargava)
- redhat: Unify genspec.sh and kernel.spec variable names (Prarit Bhargava)
- redhat/genspec.sh: Remove options and use Makefile variables (Prarit Bhargava)
- Add rebase note for 5.17 on Fedora stable (Justin M. Forbes)
- More Fedora config updates for 5.17 (Justin M. Forbes)
- redhat/configs: Disable CONFIG_MACINTOSH_DRIVERS in RHEL. (Prarit Bhargava)
- redhat: Fix "make dist-release-finish" to use the correct NVR variables (Neal Gompa) [2053836]
- Build CROS_EC Modules (Jason Montleon)
- redhat: configs: change aarch64 default dma domain to lazy (Jerry Snitselaar)
- redhat: configs: disable ATM protocols (Davide Caratti)
- configs/fedora: Enable the interconnect SC7180 driver built-in (Enric Balletbo i Serra)
- configs: clean up CONFIG_PAGE_TABLE_ISOLATION files (Ondrej Mosnacek)
- redhat: configs: enable CONFIG_INTEL_PCH_THERMAL for RHEL x86 (David Arcari)
- redhat/Makefile: Fix dist-dump-variables target (Prarit Bhargava)
- redhat/configs: Enable DEV_DAX and DEV_DAX_PMEM modules on aarch64 for fedora (D Scott Phillips)
- redhat/configs: Enable CONFIG_TRANSPARENT_HUGEPAGE on aarch64 for fedora (D Scott Phillips)
- configs/process_configs.sh: Remove orig files (Prarit Bhargava)
- redhat: configs: Disable CONFIG_MPLS for s390x/zfcpdump (Guillaume Nault)
- Fedora 5.17 configs round 1 (Justin M. Forbes)
- redhat: configs: disable the surface platform (David Arcari)
- redhat: configs: Disable team driver (Hangbin Liu) [1945477]
- configs: enable LOGITECH_FF for RHEL/CentOS too (Benjamin Tissoires)
- redhat/configs: Disable CONFIG_SENSORS_NCT6683 in RHEL for arm/aarch64 (Dean Nelson) [2041186]
- redhat: fix make {distg-brew,distg-koji} (Andrea Claudi)
- [fedora] Turn on CONFIG_VIDEO_OV5693 for sensor support (Dave Olsthoorn)
- Cleanup 'disabled' config options for RHEL (Prarit Bhargava)
- redhat: move CONFIG_ARM64_MTE to aarch64 config directory (Herton R. Krzesinski)
- Change CONFIG_TEST_BPF to a module (Justin M. Forbes)
- Change CONFIG_TEST_BPF to module in pending MR coming for proper review (Justin M. Forbes)
- redhat/configs: Enable CONFIG_TEST_BPF (Viktor Malik)
- Enable KUNIT tests for testing (Nico Pache)
- Makefile: Check PKGRELEASE size on dist-brew targets (Prarit Bhargava)
- kernel.spec: Add glibc-static build requirement (Prarit Bhargava)
- Enable iSER on s390x (Stefan Schulze Frielinghaus)
- redhat/configs: Enable CONFIG_ACER_WIRELESS (Peter Georg) [2025985]
- kabi: Add kABI macros for enum type (Čestmír Kalina) [2024595]
- kabi: expand and clarify documentation of aux structs (Čestmír Kalina) [2024595]
- kabi: introduce RH_KABI_USE_AUX_PTR (Čestmír Kalina) [2024595]
- kabi: rename RH_KABI_SIZE_AND_EXTEND to AUX (Čestmír Kalina) [2024595]
- kabi: more consistent _RH_KABI_SIZE_AND_EXTEND (Čestmír Kalina) [2024595]
- kabi: use fixed field name for extended part (Čestmír Kalina) [2024595]
- kabi: fix dereference in RH_KABI_CHECK_EXT (Čestmír Kalina) [2024595]
- kabi: fix RH_KABI_SET_SIZE macro (Čestmír Kalina) [2024595]
- kabi: expand and clarify documentation (Čestmír Kalina) [2024595]
- kabi: make RH_KABI_USE replace any number of reserved fields (Čestmír Kalina) [2024595]
- kabi: rename RH_KABI_USE2 to RH_KABI_USE_SPLIT (Čestmír Kalina) [2024595]
- kabi: change RH_KABI_REPLACE2 to RH_KABI_REPLACE_SPLIT (Čestmír Kalina) [2024595]
- kabi: change RH_KABI_REPLACE_UNSAFE to RH_KABI_BROKEN_REPLACE (Čestmír Kalina) [2024595]
- kabi: introduce RH_KABI_ADD_MODIFIER (Čestmír Kalina) [2024595]
- kabi: Include kconfig.h (Čestmír Kalina) [2024595]
- kabi: macros for intentional kABI breakage (Čestmír Kalina) [2024595]
- kabi: fix the note about terminating semicolon (Čestmír Kalina) [2024595]
- kabi: introduce RH_KABI_HIDE_INCLUDE and RH_KABI_FAKE_INCLUDE (Čestmír Kalina) [2024595]
- spec: don't overwrite auto.conf with .config (Ondrej Mosnacek)
- New configs in drivers/crypto (Fedora Kernel Team)
- Add test_hash to the mod-internal.list (Justin M. Forbes)
- configs: disable CONFIG_CRAMFS (Abhi Das) [2041184]
- spec: speed up "cp -r" when it overwrites existing files. (Denys Vlasenko)
- redhat: use centos x509.genkey file if building under centos (Herton R. Krzesinski)
- Revert "[redhat] Generate a crashkernel.default for each kernel build" (Coiby Xu)
- spec: make linux-firmware weak(er) dependency (Jan Stancek)
- rtw89: enable new driver rtw89 and device RTK8852AE (Íñigo Huguet)
- Config consolidation into common (Justin M. Forbes)
- Add packaged but empty /lib/modules/<kver>/systemtap/ (Justin M. Forbes)
- filter-modules.sh.rhel: Add ntc_thermistor to singlemods (Prarit Bhargava)
- Move CONFIG_SND_SOC_TLV320AIC31XX as it is now selected by CONFIG_SND_SOC_FSL_ASOC_CARD (Justin M. Forbes)
- Add dev_addr_lists_test to mod-internal.list (Justin M. Forbes)
- configs/fedora: Enable CONFIG_NFC_PN532_UART for use PN532 NFC module (Ziqian SUN (Zamir))
- redhat: ignore ksamples and kselftests on the badfuncs rpminspect test (Herton R. Krzesinski)
- redhat: disable upstream check for rpminspect (Herton R. Krzesinski)
- redhat: switch the vsyscall config to CONFIG_LEGACY_VSYSCALL_XONLY=y (Herton R. Krzesinski) [1876977]
- redhat: configs: increase CONFIG_DEBUG_KMEMLEAK_MEM_POOL_SIZE (Rafael Aquini)
- move CONFIG_STRICT_SIGALTSTACK_SIZE to the appropriate directory (David Arcari)
- redhat/configs: Enable CONFIG_DM_MULTIPATH_IOA for fedora (Benjamin Marzinski)
- redhat/configs: Enable CONFIG_DM_MULTIPATH_HST (Benjamin Marzinski) [2000835]
- redhat: Pull in openssl-devel as a build dependency correctly (Neal Gompa) [2034670]
- redhat/configs: Migrate ZRAM_DEF_* configs to common/ (Neal Gompa)
- redhat/configs: Enable CONFIG_CRYPTO_ZSTD (Neal Gompa) [2032758]
- Turn CONFIG_DEVMEM back off for aarch64 (Justin M. Forbes)
- Clean up excess text in Fedora config files (Justin M. Forbes)
- Fedora config updates for 5.16 (Justin M. Forbes)
- redhat/configs: enable CONFIG_INPUT_KEYBOARD for AARCH64 (Vitaly Kuznetsov)
- Fedora configs for 5.16 pt 1 (Justin M. Forbes)
- redhat/configs: NFS: disable UDP, insecure enctypes (Benjamin Coddington) [1952863]
- Update rebase-notes with dracut 5.17 information (Justin M. Forbes)
- redhat/configs: Enable CONFIG_CRYPTO_BLAKE2B (Neal Gompa) [2031547]
- Enable CONFIG_BPF_SYSCALL for zfcpdump (Jiri Olsa)
- Enable CONFIG_CIFS_SMB_DIRECT for ARK (Ronnie Sahlberg)
- mt76: enable new device MT7921E in CentOs/RHEL (Íñigo Huguet) [2004821]
- Disable CONFIG_DEBUG_PREEMPT on normal builds (Phil Auld)
- redhat/configs: Enable CONFIG_PCI_P2PDMA for ark (Myron Stowe)
- pci.h: Fix static include (Prarit Bhargava)
- Enable CONFIG_VFIO_NOIOMMU for Fedora (Justin M. Forbes)
- redhat/configs: enable CONFIG_NTB_NETDEV for ark (John W. Linville)
- drivers/pci/pci-driver.c: Fix if/ifdef typo (Prarit Bhargava)
- common: arm64: ensure all the required arm64 errata are enabled (Peter Robinson)
- kernel/rh_taint.c: Update to new messaging (Prarit Bhargava) [2019377]
- redhat/configs: enable CONFIG_AMD_PTDMA for ark (John W. Linville)
- redhat/configs: enable CONFIG_RD_ZSTD for rhel (Tao Liu) [2020132]
- fedora: build TEE as a module for all arches (Peter Robinson)
- common: build TRUSTED_KEYS in everywhere (Peter Robinson)
- redhat: make Patchlist.changelog generation conditional (Herton R. Krzesinski)
- redhat/configs: Add two new CONFIGs (Prarit Bhargava)
- redhat/configs: Remove dead CONFIG files (Prarit Bhargava)
- redhat/configs/evaluate_configs: Add find dead configs option (Prarit Bhargava)
- Add more rebase notes for Fedora 5.16 (Justin M. Forbes)
- Fedora: Feature: Retire wireless Extensions (Peter Robinson)
- fedora: arm: some SoC enablement pieces (Peter Robinson)
- fedora: arm: enable PCIE_ROCKCHIP_DW for rk35xx series (Peter Robinson)
- fedora: enable RTW89 802.11 WiFi driver (Peter Robinson)
- fedora: arm: Enable DRM_PANEL_EDP (Peter Robinson)
- fedora: sound: enable new sound drivers (Peter Robinson)
- redhat/configs: unset KEXEC_SIG for s390x zfcpdump (Coiby Xu)
- spec: Keep .BTF section in modules (Jiri Olsa)
- Fix up PREEMPT configs (Justin M. Forbes)
- New configs in drivers/media (Fedora Kernel Team)
- New configs in drivers/net/ethernet/litex (Fedora Kernel Team)
- spec: add bpf_testmod.ko to kselftests/bpf (Viktor Malik)
- New configs in drivers/net/wwan (Fedora Kernel Team)
- New configs in drivers/i2c (Fedora Kernel Team)
- redhat/docs/index.rst: Add local build information. (Prarit Bhargava)
- Fix up preempt configs (Justin M. Forbes)
- Turn on CONFIG_HID_NINTENDO for controller support (Dave Olsthoorn)
- Fedora: Enable MediaTek bluetooth pieces (Peter Robinson)
- Add rebase notes to check for PCI patches (Justin M. Forbes)
- redhat: configs: move CONFIG_ACCESSIBILITY from fedora to common (John W. Linville)
- Filter updates for hid-playstation on Fedora (Justin M. Forbes)
- Enable CONFIG_VIRT_DRIVERS for ARK (Vitaly Kuznetsov)
- redhat/configs: Enable Nitro Enclaves on aarch64 (Vitaly Kuznetsov)
- Enable e1000 in rhel9 as unsupported (Ken Cox) [2002344]
- Turn on COMMON_CLK_AXG_AUDIO for Fedora rhbz 2020481 (Justin M. Forbes)
- Fix up fedora config options from mismatch (Justin M. Forbes)
- Add nct6775 to filter-modules.sh.rhel (Justin M. Forbes)
- Enable PREEMPT_DYNAMIC for all but s390x (Justin M. Forbes)
- Add memcpy_kunit to mod-internal.list (Justin M. Forbes)
- New configs in fs/ksmbd (Fedora Kernel Team)
- Add nct6775 to Fedora filter-modules.sh (Justin M. Forbes)
- New configs in fs/ntfs3 (Fedora Kernel Team)
- Make CONFIG_IOMMU_DEFAULT_DMA_STRICT default for all but x86 (Justin M. Forbes)
- redhat/configs: enable  KEXEC_IMAGE_VERIFY_SIG for RHEL (Coiby Xu)
- redhat/configs: enable KEXEC_SIG for aarch64 RHEL (Coiby Xu) [1994858]
- Fix up fedora and pending configs for PREEMPT to end mismatch (Justin M. Forbes)
- Enable binder for fedora (Justin M. Forbes)
- Reset RHEL_RELEASE for 5.16 (Justin M. Forbes)
- redhat: configs: Update configs for vmware (Kamal Heib)
- Fedora configs for 5.15 (Justin M. Forbes)
- redhat/kernel.spec.template: don't hardcode gcov arches (Jan Stancek)
- redhat/configs: create a separate config for gcov options (Jan Stancek)
- Update documentation with FAQ and update frequency (Don Zickus)
- Document force pull option for mirroring (Don Zickus)
- Ignore the rhel9 kabi files (Don Zickus)
- Remove legacy elrdy cruft (Don Zickus)
- redhat/configs/evaluate_configs: walk cfgvariants line by line (Jan Stancek)
- redhat/configs/evaluate_configs: insert EMPTY tags at correct place (Jan Stancek)
- redhat: make dist-srpm-gcov add to BUILDOPTS (Jan Stancek)
- Build CONFIG_SPI_PXA2XX as a module on x86 (Justin M. Forbes)
- redhat/configs: enable CONFIG_BCMGENET as module (Joel Savitz)
- Fedora config updates (Justin M. Forbes)
- Enable CONFIG_FAIL_SUNRPC for debug builds (Justin M. Forbes)
- fedora: Disable fbdev drivers and use simpledrm instead (Javier Martinez Canillas)
- spec: Don't fail spec build if ksamples fails (Jiri Olsa)
- Enable CONFIG_QCOM_SCM for arm (Justin M. Forbes)
- redhat: Disable clang's integrated assembler on ppc64le and s390x (Tom Stellard)
- redhat/configs: enable CONFIG_IMA_WRITE_POLICY (Bruno Meneguele)
- Fix dist-srpm-gcov (Don Zickus)
- redhat: configs: add CONFIG_NTB and related items (John W. Linville)
- Add kfence_test to mod-internal.list (Justin M. Forbes)
- Enable KUNIT tests for redhat kernel-modules-internal (Nico Pache)
- redhat: add *-matched meta packages to rpminspect emptyrpm config (Herton R. Krzesinski)
- Use common config for NODES_SHIFT (Mark Salter)
- redhat: fix typo and make the output more silent for dist-git sync (Herton R. Krzesinski)
- Fedora NTFS config updates (Justin M. Forbes)
- Fedora 5.15 configs part 1 (Justin M. Forbes)
- Fix ordering in genspec args (Justin M. Forbes)
- redhat/configs: Enable Hyper-V guests on ARM64 (Vitaly Kuznetsov) [2007430]
- redhat: configs: Enable CONFIG_THINKPAD_LMI (Hans de Goede)
- redhat/docs: update Koji link to avoid redirect (Joel Savitz)
- redhat: add support for different profiles with dist*-brew (Herton R. Krzesinski)
- redhat: configs: Disable xtables and ipset (Phil Sutter) [1945179]
- redhat: Add mark_driver_deprecated() (Phil Sutter) [1945179]
- Change s390x CONFIG_NODES_SHIFT from 4 to 1 (Justin M. Forbes)
- Build CRYPTO_SHA3_*_S390 inline for s390 zfcpdump (Justin M. Forbes)
- redhat: move the DIST variable setting to Makefile.variables (Herton R. Krzesinski)
- redhat/kernel.spec.template: Cleanup source numbering (Prarit Bhargava)
- redhat/kernel.spec.template: Reorganize RHEL and Fedora specific files (Prarit Bhargava)
- redhat/kernel.spec.template: Add include_fedora and include_rhel variables (Prarit Bhargava)
- redhat/Makefile: Make kernel-local global (Prarit Bhargava)
- redhat/Makefile: Use flavors file (Prarit Bhargava)
- Turn on CONFIG_CPU_FREQ_GOV_SCHEDUTIL for x86 (Justin M. Forbes)
- redhat/configs: Remove CONFIG_INFINIBAND_I40IW (Kamal Heib)
- cleanup CONFIG_X86_PLATFORM_DRIVERS_INTEL (David Arcari)
- redhat: rename usage of .rhel8git.mk to .rhpkg.mk (Herton R. Krzesinski)
- Manually add pending items that need to be set due to mismatch (Justin M. Forbes)
- Clean up pending common (Justin M. Forbes)
- redhat/configs: Enable CONFIG_BLK_CGROUP_IOLATENCY & CONFIG_BLK_CGROUP_FC_APPID (Waiman Long) [2006813]
- redhat: remove kernel.changelog-8.99 file (Herton R. Krzesinski)
- redhat/configs: enable CONFIG_SQUASHFS_ZSTD which is already enabled in Fedora 34 (Tao Liu) [1998953]
- redhat: bump RHEL_MAJOR and add the changelog file for it (Herton R. Krzesinski)
- redhat: add documentation about the os-build rebase process (Herton R. Krzesinski)
- redhat/configs: enable SYSTEM_BLACKLIST_KEYRING which is already enabled in rhel8 and Fedora 34 (Coiby Xu)
- Build kernel-doc for Fedora (Justin M. Forbes)
- x86_64: Enable Elkhart Lake Quadrature Encoder Peripheral support (Prarit Bhargava)
- Update CONFIG_WERROR to disabled as it can cause issue with out of tree modules. (Justin M. Forbes)
- Fixup IOMMU configs in pending so that configs are sane again (Justin M. Forbes)
- Some initial Fedora config items for 5.15 (Justin M. Forbes)
- arm64: use common CONFIG_MAX_ZONEORDER for arm kernel (Mark Salter)
- Create Makefile.variables for a single point of configuration change (Justin M. Forbes)
- rpmspec: drop traceevent files instead of just excluding them from files list (Herton R. Krzesinski) [1967640]
- redhat/config: Enablement of CONFIG_PAPR_SCM for PowerPC (Gustavo Walbon) [1962936]
- Attempt to fix Intel PMT code (David Arcari)
- CI: Enable realtime branch testing (Veronika Kabatova)
- CI: Enable realtime checks for c9s and RHEL9 (Veronika Kabatova)
- [fs] dax: mark tech preview (Bill O'Donnell) [1995338]
- ark: wireless: enable all rtw88 pcie wirless variants (Peter Robinson)
- wireless: rtw88: move debug options to common/debug (Peter Robinson)
- fedora: minor PTP clock driver cleanups (Peter Robinson)
- common: x86: enable VMware PTP support on ark (Peter Robinson)
- [scsi] megaraid_sas: re-add certain pci-ids (Tomas Henzl)
- Disable liquidio driver on ark/rhel (Herton R. Krzesinski) [1993393]
- More Fedora config updates (Justin M. Forbes)
- Fedora config updates for 5.14 (Justin M. Forbes)
- CI: Rename ARK CI pipeline type (Veronika Kabatova)
- CI: Finish up c9s config (Veronika Kabatova)
- CI: Update ppc64le config (Veronika Kabatova)
- CI: use more templates (Veronika Kabatova)
- Filter updates for aarch64 (Justin M. Forbes)
- increase CONFIG_NODES_SHIFT for aarch64 (Chris von Recklinghausen) [1890304]
- redhat: configs: Enable CONFIG_WIRELESS_HOTKEY (Hans de Goede)
- redhat/configs: Update CONFIG_NVRAM (Desnes A. Nunes do Rosario) [1988254]
- common: serial: build in SERIAL_8250_LPSS for x86 (Peter Robinson)
- powerpc: enable CONFIG_FUNCTION_PROFILER (Diego Domingos) [1831065]
- redhat/configs: Disable Soft-RoCE driver (Kamal Heib)
- redhat/configs/evaluate_configs: Update help output (Prarit Bhargava)
- redhat/configs: Double MAX_LOCKDEP_CHAINS (Justin M. Forbes)
- fedora: configs: Fix WM5102 Kconfig (Hans de Goede)
- powerpc: enable CONFIG_POWER9_CPU (Diego Domingos) [1876436]
- redhat/configs: Fix CONFIG_VIRTIO_IOMMU to 'y' on aarch64 (Eric Auger) [1972795]
- filter-modules.sh: add more sound modules to filter (Jaroslav Kysela)
- redhat/configs: sound configuration cleanups and updates (Jaroslav Kysela)
- common: Update for CXL (Compute Express Link) configs (Peter Robinson)
- redhat: configs: disable CRYPTO_SM modules (Herton R. Krzesinski) [1990040]
- Remove fedora version of the LOCKDEP_BITS, we should use common (Justin M. Forbes)
- Re-enable sermouse for x86 (rhbz 1974002) (Justin M. Forbes)
- Fedora 5.14 configs round 1 (Justin M. Forbes)
- redhat: add gating configuration for centos stream/rhel9 (Herton R. Krzesinski)
- x86: configs: Enable CONFIG_TEST_FPU for debug kernels (Vitaly Kuznetsov) [1988384]
- redhat/configs: Move CHACHA and POLY1305 to core kernel to allow BIG_KEYS=y (root) [1983298]
- kernel.spec: fix build of samples/bpf (Jiri Benc)
- Enable OSNOISE_TRACER and TIMERLAT_TRACER (Jerome Marchand) [1979379]
- rpmspec: switch iio and gpio tools to use tools_make (Herton R. Krzesinski) [1956988]
- configs/process_configs.sh: Handle config items with no help text (Patrick Talbert)
- fedora: sound config updates for 5.14 (Peter Robinson)
- fedora: Only enable FSI drivers on POWER platform (Peter Robinson)
- The CONFIG_RAW_DRIVER has been removed from upstream (Peter Robinson)
- fedora: updates for 5.14 with a few disables for common from pending (Peter Robinson)
- fedora: migrate from MFD_TPS68470 -> INTEL_SKL_INT3472 (Peter Robinson)
- fedora: Remove STAGING_GASKET_FRAMEWORK (Peter Robinson)
- Fedora: move DRM_VMWGFX configs from ark -> common (Peter Robinson)
- fedora: arm: disabled unused FB drivers (Peter Robinson)
- fedora: don't enable FB_VIRTUAL (Peter Robinson)
- redhat/configs: Double MAX_LOCKDEP_ENTRIES (Waiman Long) [1940075]
- rpmspec: fix verbose output on kernel-devel installation (Herton R. Krzesinski) [1981406]
- Build Fedora x86s kernels with bytcr-wm5102 (Marius Hoch)
- Deleted redhat/configs/fedora/generic/x86/CONFIG_FB_HYPERV (Patrick Lang)
- rpmspec: correct the ghost initramfs attributes (Herton R. Krzesinski) [1977056]
- rpmspec: amend removal of depmod created files to include modules.builtin.alias.bin (Herton R. Krzesinski) [1977056]
- configs: remove duplicate CONFIG_DRM_HYPERV file (Patrick Talbert)
- CI: use common code for merge and release (Don Zickus)
- rpmspec: add release string to kernel doc directory name (Jan Stancek)
- redhat/configs: Add CONFIG_INTEL_PMT_CRASHLOG (Michael Petlan) [1880486]
- redhat/configs: Add CONFIG_INTEL_PMT_TELEMETRY (Michael Petlan) [1880486]
- redhat/configs: Add CONFIG_MFD_INTEL_PMT (Michael Petlan) [1880486]
- redhat/configs: enable CONFIG_BLK_DEV_ZONED (Ming Lei) [1638087]
- Add --with clang_lto option to build the kernel with Link Time Optimizations (Tom Stellard)
- common: disable DVB_AV7110 and associated pieces (Peter Robinson)
- Fix fedora-only config updates (Don Zickus)
- Fedor config update for new option (Justin M. Forbes)
- redhat/configs: Enable stmmac NIC for x86_64 (Mark Salter)
- all: hyperv: use the DRM driver rather than FB (Peter Robinson)
- all: hyperv: unify the Microsoft HyperV configs (Peter Robinson)
- all: VMWare: clean up VMWare configs (Peter Robinson)
- Update CONFIG_ARM_FFA_TRANSPORT (Patrick Talbert)
- CI: Handle all mirrors (Veronika Kabatova)
- Turn on CONFIG_STACKTRACE for s390x zfpcdump kernels (Justin M. Forbes)
- arm64: switch ark kernel to 4K pagesize (Mark Salter)
- Disable AMIGA_PARTITION and KARMA_PARTITION (Prarit Bhargava) [1802694]
- all: unify and cleanup i2c TPM2 modules (Peter Robinson)
- redhat/configs: Set CONFIG_VIRTIO_IOMMU on aarch64 (Eric Auger) [1972795]
- redhat/configs: Disable CONFIG_RT_GROUP_SCHED in rhel config (Phil Auld)
- redhat/configs: enable KEXEC_SIG which is already enabled in RHEL8 for s390x and x86_64 (Coiby Xu) [1976835]
- rpmspec: do not BuildRequires bpftool on noarch (Herton R. Krzesinski)
- redhat/configs: disable {IMA,EVM}_LOAD_X509 (Bruno Meneguele) [1977529]
- redhat: add secureboot CA certificate to trusted kernel keyring (Bruno Meneguele)
- redhat/configs: enable IMA_ARCH_POLICY for aarch64 and s390x (Bruno Meneguele)
- redhat/configs: Enable CONFIG_MLXBF_GIGE on aarch64 (Alaa Hleihel) [1858599]
- common: enable STRICT_MODULE_RWX everywhere (Peter Robinson)
- COMMON_CLK_STM32MP157_SCMI is bool and selects COMMON_CLK_SCMI (Justin M. Forbes)
- kernel.spec: Add kernel{,-debug}-devel-matched meta packages (Timothée Ravier)
- Turn off with_selftests for Fedora (Justin M. Forbes)
- Don't build bpftool on Fedora (Justin M. Forbes)
- Fix location of syscall scripts for kernel-devel (Justin M. Forbes)
- fedora: arm: Enable some i.MX8 options (Peter Robinson)
- Enable Landlock for Fedora (Justin M. Forbes)
- Filter update for Fedora aarch64 (Justin M. Forbes)
- rpmspec: only build debug meta packages where we build debug ones (Herton R. Krzesinski)
- rpmspec: do not BuildRequires bpftool on nobuildarches (Herton R. Krzesinski)
- redhat/configs: Consolidate CONFIG_HMC_DRV in the common s390x folder (Thomas Huth) [1976270]
- redhat/configs: Consolidate CONFIG_EXPOLINE_OFF in the common folder (Thomas Huth) [1976270]
- redhat/configs: Move CONFIG_HW_RANDOM_S390 into the s390x/ subfolder (Thomas Huth) [1976270]
- redhat/configs: Disable CONFIG_HOTPLUG_PCI_SHPC in the Fedora settings (Thomas Huth) [1976270]
- redhat/configs: Remove the non-existent CONFIG_NO_BOOTMEM switch (Thomas Huth) [1976270]
- redhat/configs: Compile the virtio-console as a module on s390x (Thomas Huth) [1976270]
- redhat/configs: Enable CONFIG_S390_CCW_IOMMU and CONFIG_VFIO_CCW for ARK, too (Thomas Huth) [1976270]
- Revert "Merge branch 'ec_fips' into 'os-build'" (Vladis Dronov) [1947240]
- Fix typos in fedora filters (Justin M. Forbes)
- More filtering for Fedora (Justin M. Forbes)
- Fix Fedora module filtering for spi-altera-dfl (Justin M. Forbes)
- Fedora 5.13 config updates (Justin M. Forbes)
- fedora: cleanup TCG_TIS_I2C_CR50 (Peter Robinson)
- fedora: drop duplicate configs (Peter Robinson)
- More Fedora config updates for 5.13 (Justin M. Forbes)
- redhat/configs: Enable needed drivers for BlueField SoC on aarch64 (Alaa Hleihel) [1858592 1858594 1858596]
- redhat: Rename mod-blacklist.sh to mod-denylist.sh (Prarit Bhargava)
- redhat/configs: enable CONFIG_NET_ACT_MPLS (Marcelo Ricardo Leitner)
- configs: Enable CONFIG_DEBUG_KERNEL for zfcpdump (Jiri Olsa)
- kernel.spec: Add support to use vmlinux.h (Don Zickus)
- spec: Add vmlinux.h to kernel-devel package (Jiri Olsa)
- Turn off DRM_XEN_FRONTEND for Fedora as we had DRM_XEN off already (Justin M. Forbes)
- Fedora 5.13 config updates pt 3 (Justin M. Forbes)
- all: enable ath11k wireless modules (Peter Robinson)
- all: Enable WWAN and associated MHI bus pieces (Peter Robinson)
- spec: Enable sefltests rpm build (Jiri Olsa)
- spec: Allow bpf selftest/samples to fail (Jiri Olsa)
- kvm: Add kvm_stat.service file and kvm_stat logrotate config to the tools (Jiri Benc)
- kernel.spec: Add missing source files to kernel-selftests-internal (Jiri Benc)
- kernel.spec: selftests: add net/forwarding to TARGETS list (Jiri Benc)
- kernel.spec: selftests: add build requirement on libmnl-devel (Jiri Benc)
- kernel.spec: add action.o to kernel-selftests-internal (Jiri Benc)
- kernel.spec: avoid building bpftool repeatedly (Jiri Benc)
- kernel.spec: selftests require python3 (Jiri Benc)
- kernel.spec: skip selftests that failed to build (Jiri Benc)
- kernel.spec: fix installation of bpf selftests (Jiri Benc)
- redhat: fix samples and selftests make options (Jiri Benc)
- kernel.spec: enable mptcp selftests for kernel-selftests-internal (Jiri Benc)
- kernel.spec: Do not export shared objects from libexecdir to RPM Provides (Jiri Benc)
- kernel.spec: add missing dependency for the which package (Jiri Benc)
- kernel.spec: add netfilter selftests to kernel-selftests-internal (Jiri Benc)
- kernel.spec: move slabinfo and page_owner_sort debuginfo to tools-debuginfo (Jiri Benc)
- kernel.spec: package and ship VM tools (Jiri Benc)
- configs: enable CONFIG_PAGE_OWNER (Jiri Benc)
- kernel.spec: add coreutils (Jiri Benc)
- kernel.spec: add netdevsim driver selftests to kernel-selftests-internal (Jiri Benc)
- redhat/Makefile: Clean out the --without flags from the baseonly rule (Jiri Benc)
- kernel.spec: Stop building unnecessary rpms for baseonly builds (Jiri Benc)
- kernel.spec: disable more kabi switches for gcov build (Jiri Benc)
- kernel.spec: Rename kabi-dw base (Jiri Benc)
- kernel.spec: Fix error messages during build of zfcpdump kernel (Jiri Benc)
- kernel.spec: perf: remove bpf examples (Jiri Benc)
- kernel.spec: selftests should not depend on modules-internal (Jiri Benc)
- kernel.spec: build samples (Jiri Benc)
- kernel.spec: tools: sync missing options with RHEL 8 (Jiri Benc)
- redhat/configs: nftables: Enable extra flowtable symbols (Phil Sutter)
- redhat/configs: Sync netfilter options with RHEL8 (Phil Sutter)
- Fedora 5.13 config updates pt 2 (Justin M. Forbes)
- Move CONFIG_ARCH_INTEL_SOCFPGA up a level for Fedora (Justin M. Forbes)
- fedora: enable the Rockchip rk3399 pcie drivers (Peter Robinson)
- Fedora 5.13 config updates pt 1 (Justin M. Forbes)
- Fix version requirement from opencsd-devel buildreq (Justin M. Forbes)
- configs/ark/s390: set CONFIG_MARCH_Z14 and CONFIG_TUNE_Z15 (Philipp Rudo) [1876435]
- configs/common/s390: Clean up CONFIG_{MARCH,TUNE}_Z* (Philipp Rudo)
- configs/process_configs.sh: make use of dummy-tools (Philipp Rudo)
- configs/common: disable CONFIG_INIT_STACK_ALL_{PATTERN,ZERO} (Philipp Rudo)
- configs/common/aarch64: disable CONFIG_RELR (Philipp Rudo)
- redhat/config: enable STMICRO nic for RHEL (Mark Salter)
- redhat/configs: Enable ARCH_TEGRA on RHEL (Mark Salter)
- redhat/configs: enable IMA_KEXEC for supported arches (Bruno Meneguele)
- redhat/configs: enable INTEGRITY_SIGNATURE to all arches (Bruno Meneguele)
- configs: enable CONFIG_LEDS_BRIGHTNESS_HW_CHANGED (Benjamin Tissoires)
- RHEL: disable io_uring support (Jeff Moyer) [1964537]
- all: Changing CONFIG_UV_SYSFS to build uv_sysfs.ko as a loadable module. (Frank Ramsay)
- Enable NITRO_ENCLAVES on RHEL (Vitaly Kuznetsov)
- Update the Quick Start documentation (David Ward)
- redhat/configs: Set PVPANIC_MMIO for x86 and PVPANIC_PCI for aarch64 (Eric Auger) [1961178]
- bpf: Fix unprivileged_bpf_disabled setup (Jiri Olsa)
- Enable CONFIG_BPF_UNPRIV_DEFAULT_OFF (Jiri Olsa)
- configs/common/s390: disable CONFIG_QETH_{OSN,OSX} (Philipp Rudo) [1903201]
- nvme: nvme_mpath_init remove multipath check (Mike Snitzer)
- team: mark team driver as deprecated (Hangbin Liu) [1945477]
- Make CRYPTO_EC also builtin (Simo Sorce) [1947240]
- Do not hard-code a default value for DIST (David Ward)
- Override %%{debugbuildsenabled} if the --with-release option is used (David Ward)
- Improve comments in SPEC file, and move some option tests and macros (David Ward)
- configs: enable CONFIG_EXFAT_FS (Pavel Reichl) [1943423]
- Revert s390x/zfcpdump part of a9d179c40281 and ecbfddd98621 (Vladis Dronov)
- Embed crypto algos, modes and templates needed in the FIPS mode (Vladis Dronov) [1947240]
- configs: Add and enable CONFIG_HYPERV_TESTING for debug kernels (Mohammed Gamal)
- mm/cma: mark CMA on x86_64 tech preview and print RHEL-specific infos (David Hildenbrand) [1945002]
- configs: enable CONFIG_CMA on x86_64 in ARK (David Hildenbrand) [1945002]
- rpmspec: build debug-* meta-packages if debug builds are disabled (Herton R. Krzesinski)
- UIO: disable unused config options (Aristeu Rozanski) [1957819]
- ARK-config: Make amd_pinctrl module builtin (Hans de Goede)
- rpmspec: revert/drop content hash for kernel-headers (Herton R. Krzesinski)
- rpmspec: fix check that calls InitBuildVars (Herton R. Krzesinski)
- fedora: enable zonefs (Damien Le Moal)
- redhat: load specific ARCH keys to INTEGRITY_PLATFORM_KEYRING (Bruno Meneguele)
- redhat: enable INTEGRITY_TRUSTED_KEYRING across all variants (Bruno Meneguele)
- redhat: enable SYSTEM_BLACKLIST_KEYRING across all variants (Bruno Meneguele)
- redhat: enable INTEGRITY_ASYMMETRIC_KEYS across all variants (Bruno Meneguele)
- Remove unused boot loader specification files (David Ward)
- redhat/configs: Enable mlx5 IPsec and TLS offloads (Alaa Hleihel) [1869674 1957636]
- common: disable Apple Silicon generally (Peter Robinson)
- cleanup Intel's FPGA configs (Peter Robinson)
- common: move PTP KVM support from ark to common (Peter Robinson)
- Enable CONFIG_DRM_AMDGPU_USERPTR for everyone (Justin M. Forbes)
- redhat: add initial rpminspect configuration (Herton R. Krzesinski)
- fedora: arm updates for 5.13 (Peter Robinson)
- fedora: Enable WWAN and associated MHI bits (Peter Robinson)
- Update CONFIG_MODPROBE_PATH to /usr/sbin (Justin Forbes)
- Fedora set modprobe path (Justin M. Forbes)
- Keep sctp and l2tp modules in modules-extra (Don Zickus)
- Fix ppc64le cross build packaging (Don Zickus)
- Fedora: Make amd_pinctrl module builtin (Hans de Goede)
- Keep CONFIG_KASAN_HW_TAGS off for aarch64 debug configs (Justin M. Forbes)
- New configs in drivers/bus (Fedora Kernel Team)
- RHEL: Don't build KVM PR module on ppc64 (David Gibson) [1930649]
- Flip CONFIG_USB_ROLE_SWITCH from m to y (Justin M. Forbes)
- Set valid options for CONFIG_FW_LOADER_USER_HELPER (Justin M. Forbes)
- Clean up CONFIG_FB_MODE_HELPERS (Justin M. Forbes)
- Turn off CONFIG_VFIO for the s390x zfcpdump kernel (Justin M. Forbes)
- Delete unused CONFIG_SND_SOC_MAX98390 pending-common (Justin M. Forbes)
- Update pending-common configs, preparing to set correctly (Justin M. Forbes)
- Update fedora filters for surface (Justin M. Forbes)
- Build CONFIG_CRYPTO_ECDSA inline for s390x zfcpdump (Justin M. Forbes)
- Replace "flavour" where "variant" is meant instead (David Ward)
- Drop the %%{variant} macro and fix --with-vanilla (David Ward)
- Fix syntax of %%kernel_variant_files (David Ward)
- Change description of --without-vdso-install to fix typo (David Ward)
- Config updates to work around mismatches (Justin M. Forbes)
- CONFIG_SND_SOC_FSL_ASOC_CARD selects CONFIG_MFD_WM8994 now (Justin M. Forbes)
- wireguard: disable in FIPS mode (Hangbin Liu) [1940794]
- Enable mtdram for fedora (rhbz 1955916) (Justin M. Forbes)
- Remove reference to bpf-helpers man page (Justin M. Forbes)
- Fedora: enable more modules for surface devices (Dave Olsthoorn)
- Fix Fedora config mismatch for CONFIG_FSL_ENETC_IERB (Justin M. Forbes)
- hardlink is in /usr/bin/ now (Justin M. Forbes)
- Ensure CONFIG_KVM_BOOK3S_64_PR stays on in Fedora, even if it is turned off in RHEL (Justin M. Forbes)
- Set date in package release from repository commit, not system clock (David Ward)
- Use a better upstream tarball filename for snapshots (David Ward)
- Don't create empty pending-common files on pending-fedora commits (Don Zickus)
- nvme: decouple basic ANA log page re-read support from native multipathing (Mike Snitzer)
- nvme: allow local retry and proper failover for REQ_FAILFAST_TRANSPORT (Mike Snitzer)
- nvme: Return BLK_STS_TARGET if the DNR bit is set (Mike Snitzer)
- Add redhat/configs/pending-common/generic/s390x/zfcpdump/CONFIG_NETFS_SUPPORT (Justin M. Forbes)
- Create ark-latest branch last for CI scripts (Don Zickus)
- Replace /usr/libexec/platform-python with /usr/bin/python3 (David Ward)
- Turn off ADI_AXI_ADC and AD9467 which now require CONFIG_OF (Justin M. Forbes)
- Export ark infrastructure files (Don Zickus)
- docs: Update docs to reflect newer workflow. (Don Zickus)
- Use upstream/master for merge-base with fallback to master (Don Zickus)
- Fedora: Turn off the SND_INTEL_BYT_PREFER_SOF option (Hans de Goede)
- filter-modules.sh.fedora: clean up "netprots" (Paul Bolle)
- filter-modules.sh.fedora: clean up "scsidrvs" (Paul Bolle)
- filter-*.sh.fedora: clean up "ethdrvs" (Paul Bolle)
- filter-*.sh.fedora: clean up "driverdirs" (Paul Bolle)
- filter-*.sh.fedora: remove incorrect entries (Paul Bolle)
- filter-*.sh.fedora: clean up "singlemods" (Paul Bolle)
- filter-modules.sh.fedora: drop unused list "iiodrvs" (Paul Bolle)
- Update mod-internal to fix depmod issue (Nico Pache)
- Turn on CONFIG_VDPA_SIM_NET (rhbz 1942343) (Justin M. Forbes)
- New configs in drivers/power (Fedora Kernel Team)
- Turn on CONFIG_NOUVEAU_DEBUG_PUSH for debug configs (Justin M. Forbes)
- Turn off KFENCE sampling by default for Fedora (Justin M. Forbes)
- Fedora config updates round 2 (Justin M. Forbes)
- New configs in drivers/soc (Jeremy Cline)
- filter-modules.sh: Fix copy/paste error 'input' (Paul Bolle)
- Update module filtering for 5.12 kernels (Justin M. Forbes)
- Fix genlog.py to ensure that comments retain "%%" characters. (Mark Mielke)
- New configs in drivers/leds (Fedora Kernel Team)
- Limit CONFIG_USB_CDNS_SUPPORT to x86_64 and arm in Fedora (David Ward)
- Fedora: Enable CHARGER_GPIO on aarch64 too (Peter Robinson)
- Fedora config updates (Justin M. Forbes)
- wireguard: mark as Tech Preview (Hangbin Liu) [1613522]
- configs: enable CONFIG_WIREGUARD in ARK (Hangbin Liu) [1613522]
- Remove duplicate configs acroos fedora, ark and common (Don Zickus)
- Combine duplicate configs across ark and fedora into common (Don Zickus)
- common/ark: cleanup and unify the parport configs (Peter Robinson)
- iommu/vt-d: enable INTEL_IDXD_SVM for both fedora and rhel (Jerry Snitselaar)
- REDHAT: coresight: etm4x: Disable coresight on HPE Apollo 70 (Jeremy Linton)
- configs/common/generic: disable CONFIG_SLAB_MERGE_DEFAULT (Rafael Aquini)
- Remove _legacy_common_support (Justin M. Forbes)
- redhat/mod-blacklist.sh: Fix floppy blacklisting (Hans de Goede)
- New configs in fs/pstore (CKI@GitLab)
- New configs in arch/powerpc (Fedora Kernel Team)
- configs: enable BPF LSM on Fedora and ARK (Ondrej Mosnacek)
- configs: clean up LSM configs (Ondrej Mosnacek)
- New configs in drivers/platform (CKI@GitLab)
- New configs in drivers/firmware (CKI@GitLab)
- New configs in drivers/mailbox (Fedora Kernel Team)
- New configs in drivers/net/phy (Justin M. Forbes)
- Update CONFIG_DM_MULTIPATH_IOA (Augusto Caringi)
- New configs in mm/Kconfig (CKI@GitLab)
- New configs in arch/powerpc (Jeremy Cline)
- New configs in arch/powerpc (Jeremy Cline)
- New configs in drivers/input (Fedora Kernel Team)
- New configs in net/bluetooth (Justin M. Forbes)
- New configs in drivers/clk (Fedora Kernel Team)
- New configs in init/Kconfig (Jeremy Cline)
- redhat: allow running fedora-configs and rh-configs targets outside of redhat/ (Herton R. Krzesinski)
- all: unify the disable of goldfish (android emulation platform) (Peter Robinson)
- common: minor cleanup/de-dupe of dma/dmabuf debug configs (Peter Robinson)
- common/ark: these drivers/arches were removed in 5.12 (Peter Robinson)
- Correct kernel-devel make prepare build for 5.12. (Paulo E. Castro)
- redhat: add initial support for centos stream dist-git sync on Makefiles (Herton R. Krzesinski)
- redhat/configs: Enable CONFIG_SCHED_STACK_END_CHECK for Fedora and ARK (Josh Poimboeuf) [1856174]
- CONFIG_VFIO now selects IOMMU_API instead of depending on it, causing several config mismatches for the zfcpdump kernel (Justin M. Forbes)
- Turn off weak-modules for Fedora (Justin M. Forbes)
- redhat: enable CONFIG_FW_LOADER_COMPRESS for ARK (Herton R. Krzesinski) [1939095]
- Fedora: filters: update to move dfl-emif to modules (Peter Robinson)
- drop duplicate DEVFREQ_GOV_SIMPLE_ONDEMAND config (Peter Robinson)
- efi: The EFI_VARS is legacy and now x86 only (Peter Robinson)
- common: enable RTC_SYSTOHC to supplement update_persistent_clock64 (Peter Robinson)
- generic: arm: enable SCMI for all options (Peter Robinson)
- fedora: the PCH_CAN driver is x86-32 only (Peter Robinson)
- common: disable legacy CAN device support (Peter Robinson)
- common: Enable Microchip MCP251x/MCP251xFD CAN controllers (Peter Robinson)
- common: Bosch MCAN support for Intel Elkhart Lake (Peter Robinson)
- common: enable CAN_PEAK_PCIEFD PCI-E driver (Peter Robinson)
- common: disable CAN_PEAK_PCIEC PCAN-ExpressCard (Peter Robinson)
- common: enable common CAN layer 2 protocols (Peter Robinson)
- ark: disable CAN_LEDS option (Peter Robinson)
- Fedora: Turn on SND_SOC_INTEL_SKYLAKE_HDAUDIO_CODEC option (Hans de Goede)
- Fedora: enable modules for surface devices (Dave Olsthoorn)
- Turn on SND_SOC_INTEL_SOUNDWIRE_SOF_MACH for Fedora again (Justin M. Forbes)
- common: fix WM8804 codec dependencies (Peter Robinson)
- Build SERIO_SERPORT as a module (Peter Robinson)
- input: touchscreen: move ELO and Wacom serial touchscreens to x86 (Peter Robinson)
- Sync serio touchscreens for non x86 architectures to the same as ARK (Peter Robinson)
- Only enable SERIO_LIBPS2 on x86 (Peter Robinson)
- Only enable PC keyboard controller and associated keyboard on x86 (Peter Robinson)
- Generic: Mouse: Tweak generic serial mouse options (Peter Robinson)
- Only enable PS2 Mouse options on x86 (Peter Robinson)
- Disable bluetooth highspeed by default (Peter Robinson)
- Fedora: A few more general updates for 5.12 window (Peter Robinson)
- Fedora: Updates for 5.12 merge window (Peter Robinson)
- Fedora: remove dead options that were removed upstream (Peter Robinson)
- redhat: remove CONFIG_DRM_PANEL_XINGBANGDA_XBD599 (Herton R. Krzesinski)
- New configs in arch/powerpc (Fedora Kernel Team)
- Turn on CONFIG_PPC_QUEUED_SPINLOCKS as it is default upstream now (Justin M. Forbes)
- Update pending-common configs to address new upstream config deps (Justin M. Forbes)
- rpmspec: ship gpio-watch.debug in the proper debuginfo package (Herton R. Krzesinski)
- Removed description text as a comment confuses the config generation (Justin M. Forbes)
- New configs in drivers/dma-buf (Jeremy Cline)
- Fedora: ARMv7: build for 16 CPUs. (Peter Robinson)
- Fedora: only enable DEBUG_HIGHMEM on debug kernels (Peter Robinson)
- process_configs.sh: fix find/xargs data flow (Ondrej Mosnacek)
- Fedora config update (Justin M. Forbes)
- fedora: minor arm sound config updates (Peter Robinson)
- Fix trailing white space in redhat/configs/fedora/generic/CONFIG_SND_INTEL_BYT_PREFER_SOF (Justin M. Forbes)
- Add a redhat/rebase-notes.txt file (Hans de Goede)
- Turn on SND_INTEL_BYT_PREFER_SOF for Fedora (Hans de Goede)
- CI: Drop MR ID from the name variable (Veronika Kabatova)
- redhat: add DUP and kpatch certificates to system trusted keys for RHEL build (Herton R. Krzesinski)
- The comments in CONFIG_USB_RTL8153_ECM actually turn off CONFIG_USB_RTL8152 (Justin M. Forbes)
- Update CKI pipeline project (Veronika Kabatova)
- Turn off additional KASAN options for Fedora (Justin M. Forbes)
- Rename the master branch to rawhide for Fedora (Justin M. Forbes)
- Makefile targets for packit integration (Ben Crocker)
- Turn off KASAN for rawhide debug builds (Justin M. Forbes)
- New configs in arch/arm64 (Justin Forbes)
- Remove deprecated Intel MIC config options (Peter Robinson)
- redhat: replace inline awk script with genlog.py call (Herton R. Krzesinski)
- redhat: add genlog.py script (Herton R. Krzesinski)
- kernel.spec.template - fix use_vdso usage (Ben Crocker)
- redhat: remove remaining references of CONFIG_RH_DISABLE_DEPRECATED (Herton R. Krzesinski)
- Turn off vdso_install for ppc (Justin M. Forbes)
- Remove bpf-helpers.7 from bpftool package (Jiri Olsa)
- New configs in lib/Kconfig.debug (Fedora Kernel Team)
- Turn off CONFIG_VIRTIO_CONSOLE for s390x zfcpdump (Justin M. Forbes)
- New configs in drivers/clk (Justin M. Forbes)
- Keep VIRTIO_CONSOLE on s390x available. (Jakub Čajka)
- New configs in lib/Kconfig.debug (Jeremy Cline)
- Fedora 5.11 config updates part 4 (Justin M. Forbes)
- Fedora 5.11 config updates part 3 (Justin M. Forbes)
- Fedora 5.11 config updates part 2 (Justin M. Forbes)
- Update internal (test) module list from RHEL-8 (Joe Lawrence) [1915073]
- Fix USB_XHCI_PCI regression (Justin M. Forbes)
- fedora: fixes for ARMv7 build issue by disabling HIGHPTE (Peter Robinson)
- all: s390x: Increase CONFIG_PCI_NR_FUNCTIONS to 512 (#1888735) (Dan Horák)
- Fedora 5.11 configs pt 1 (Justin M. Forbes)
- redhat: avoid conflict with mod-blacklist.sh and released_kernel defined (Herton R. Krzesinski)
- redhat: handle certificate files conditionally as done for src.rpm (Herton R. Krzesinski)
- specfile: add %%{?_smp_mflags} to "make headers_install" in tools/testing/selftests (Denys Vlasenko)
- specfile: add %%{?_smp_mflags} to "make samples/bpf/" (Denys Vlasenko)
- Run MR testing in CKI pipeline (Veronika Kabatova)
- Reword comment (Nicolas Chauvet)
- Add with_cross_arm conditional (Nicolas Chauvet)
- Redefines __strip if with_cross (Nicolas Chauvet)
- fedora: only enable ACPI_CONFIGFS, ACPI_CUSTOM_METHOD in debug kernels (Peter Robinson)
- fedora: User the same EFI_CUSTOM_SSDT_OVERLAYS as ARK (Peter Robinson)
- all: all arches/kernels enable the same DMI options (Peter Robinson)
- all: move SENSORS_ACPI_POWER to common/generic (Peter Robinson)
- fedora: PCIE_HISI_ERR is already in common (Peter Robinson)
- all: all ACPI platforms enable ATA_ACPI so move it to common (Peter Robinson)
- all: x86: move shared x86 acpi config options to generic (Peter Robinson)
- All: x86: Move ACPI_VIDEO to common/x86 (Peter Robinson)
- All: x86: Enable ACPI_DPTF (Intel DPTF) (Peter Robinson)
- All: enable ACPI_BGRT for all ACPI platforms. (Peter Robinson)
- All: Only build ACPI_EC_DEBUGFS for debug kernels (Peter Robinson)
- All: Disable Intel Classmate PC ACPI_CMPC option (Peter Robinson)
- cleanup: ACPI_PROCFS_POWER was removed upstream (Peter Robinson)
- All: ACPI: De-dupe the ACPI options that are the same across ark/fedora on x86/arm (Peter Robinson)
- Enable the vkms module in Fedora (Jeremy Cline)
- Fedora: arm updates for 5.11 and general cross Fedora cleanups (Peter Robinson)
- Add gcc-c++ to BuildRequires (Justin M. Forbes)
- Update CONFIG_KASAN_HW_TAGS (Justin M. Forbes)
- fedora: arm: move generic power off/reset to all arm (Peter Robinson)
- fedora: ARMv7: build in DEVFREQ_GOV_SIMPLE_ONDEMAND until I work out why it's changed (Peter Robinson)
- fedora: cleanup joystick_adc (Peter Robinson)
- fedora: update some display options (Peter Robinson)
- fedora: arm: enable TI PRU options (Peter Robinson)
- fedora: arm: minor exynos plaform updates (Peter Robinson)
- arm: SoC: disable Toshiba Visconti SoC (Peter Robinson)
- common: disable ARCH_BCM4908 (NFC) (Peter Robinson)
- fedora: minor arm config updates (Peter Robinson)
- fedora: enable Tegra 234 SoC (Peter Robinson)
- fedora: arm: enable new Hikey 3xx options (Peter Robinson)
- Fedora: USB updates (Peter Robinson)
- fedora: enable the GNSS receiver subsystem (Peter Robinson)
- Remove POWER_AVS as no longer upstream (Peter Robinson)
- Cleanup RESET_RASPBERRYPI (Peter Robinson)
- Cleanup GPIO_CDEV_V1 options. (Peter Robinson)
- fedora: arm crypto updates (Peter Robinson)
- CONFIG_KASAN_HW_TAGS for aarch64 (Justin M. Forbes)
- Fedora: cleanup PCMCIA configs, move to x86 (Peter Robinson)
- New configs in drivers/rtc (Fedora Kernel Team)
- redhat/configs: Enable CONFIG_GCC_PLUGIN_STRUCTLEAK_BYREF_ALL (Josh Poimboeuf) [1856176]
- redhat/configs: Enable CONFIG_GCC_PLUGIN_STRUCTLEAK (Josh Poimboeuf) [1856176]
- redhat/configs: Enable CONFIG_GCC_PLUGINS on ARK (Josh Poimboeuf) [1856176]
- redhat/configs: Enable CONFIG_KASAN on Fedora (Josh Poimboeuf) [1856176]
- New configs in init/Kconfig (Fedora Kernel Team)
- build_configs.sh: Fix syntax flagged by shellcheck (Ben Crocker)
- genspec.sh: Fix syntax flagged by shellcheck (Ben Crocker)
- mod-blacklist.sh: Fix syntax flagged by shellcheck (Ben Crocker)
- Enable Speakup accessibility driver (Justin M. Forbes)
- New configs in init/Kconfig (Fedora Kernel Team)
- Fix fedora config mismatch due to dep changes (Justin M. Forbes)
- New configs in drivers/crypto (Jeremy Cline)
- Remove duplicate ENERGY_MODEL configs (Peter Robinson)
- This is selected by PCIE_QCOM so must match (Justin M. Forbes)
- drop unused BACKLIGHT_GENERIC (Peter Robinson)
- Remove cp instruction already handled in instruction below. (Paulo E. Castro)
- Add all the dependencies gleaned from running `make prepare` on a bloated devel kernel. (Paulo E. Castro)
- Add tools to path mangling script. (Paulo E. Castro)
- Remove duplicate cp statement which is also not specific to x86. (Paulo E. Castro)
- Correct orc_types failure whilst running `make prepare` https://bugzilla.redhat.com/show_bug.cgi?id=1882854 (Paulo E. Castro)
- redhat: ark: enable CONFIG_IKHEADERS (Jiri Olsa)
- Add missing '$' sign to (GIT) in redhat/Makefile (Augusto Caringi)
- Remove filterdiff and use native git instead (Don Zickus)
- New configs in net/sched (Justin M. Forbes)
- New configs in drivers/mfd (CKI@GitLab)
- New configs in drivers/mfd (Fedora Kernel Team)
- New configs in drivers/firmware (Fedora Kernel Team)
- Temporarily backout parallel xz script (Justin M. Forbes)
- redhat: explicitly disable CONFIG_IMA_APPRAISE_SIGNED_INIT (Bruno Meneguele)
- redhat: enable CONFIG_EVM_LOAD_X509 on ARK (Bruno Meneguele)
- redhat: enable CONFIG_EVM_ATTR_FSUUID on ARK (Bruno Meneguele)
- redhat: enable CONFIG_EVM in all arches and flavors (Bruno Meneguele)
- redhat: enable CONFIG_IMA_LOAD_X509 on ARK (Bruno Meneguele)
- redhat: set CONFIG_IMA_DEFAULT_HASH to SHA256 (Bruno Meneguele)
- redhat: enable CONFIG_IMA_SECURE_AND_OR_TRUSTED_BOOT (Bruno Meneguele)
- redhat: enable CONFIG_IMA_READ_POLICY on ARK (Bruno Meneguele)
- redhat: set default IMA template for all ARK arches (Bruno Meneguele)
- redhat: enable CONFIG_IMA_DEFAULT_HASH_SHA256 for all flavors (Bruno Meneguele)
- redhat: disable CONFIG_IMA_DEFAULT_HASH_SHA1 (Bruno Meneguele)
- redhat: enable CONFIG_IMA_ARCH_POLICY for ppc and x86 (Bruno Meneguele)
- redhat: enable CONFIG_IMA_APPRAISE_MODSIG (Bruno Meneguele)
- redhat: enable CONFIG_IMA_APPRAISE_BOOTPARAM (Bruno Meneguele)
- redhat: enable CONFIG_IMA_APPRAISE (Bruno Meneguele)
- redhat: enable CONFIG_INTEGRITY for aarch64 (Bruno Meneguele)
- kernel: Update some missing KASAN/KCSAN options (Jeremy Linton)
- kernel: Enable coresight on aarch64 (Jeremy Linton)
- Update CONFIG_INET6_ESPINTCP (Justin Forbes)
- New configs in net/ipv6 (Justin M. Forbes)
- fedora: move CONFIG_RTC_NVMEM options from ark to common (Peter Robinson)
- configs: Enable CONFIG_DEBUG_INFO_BTF (Don Zickus)
- fedora: some minor arm audio config tweaks (Peter Robinson)
- Ship xpad with default modules on Fedora and RHEL (Bastien Nocera)
- Fedora: Only enable legacy serial/game port joysticks on x86 (Peter Robinson)
- Fedora: Enable the options required for the Librem 5 Phone (Peter Robinson)
- Fedora config update (Justin M. Forbes)
- Fedora config change because CONFIG_FSL_DPAA2_ETH now selects CONFIG_FSL_XGMAC_MDIO (Justin M. Forbes)
- redhat: generic  enable CONFIG_INET_MPTCP_DIAG (Davide Caratti)
- Fedora config update (Justin M. Forbes)
- Enable NANDSIM for Fedora (Justin M. Forbes)
- Re-enable CONFIG_ACPI_TABLE_UPGRADE for Fedora since upstream disables this if secureboot is active (Justin M. Forbes)
- Ath11k related config updates (Justin M. Forbes)
- Fedora config updates for ath11k (Justin M. Forbes)
- Turn on ATH11K for Fedora (Justin M. Forbes)
- redhat: enable CONFIG_INTEL_IOMMU_SVM (Jerry Snitselaar)
- More Fedora config fixes (Justin M. Forbes)
- Fedora 5.10 config updates (Justin M. Forbes)
- Fedora 5.10 configs round 1 (Justin M. Forbes)
- Fedora config updates (Justin M. Forbes)
- Allow kernel-tools to build without selftests (Don Zickus)
- Allow building of kernel-tools standalone (Don Zickus)
- redhat: ark: disable CONFIG_NET_ACT_CTINFO (Davide Caratti)
- redhat: ark: disable CONFIG_NET_SCH_TEQL (Davide Caratti)
- redhat: ark: disable CONFIG_NET_SCH_SFB (Davide Caratti)
- redhat: ark: disable CONFIG_NET_SCH_QFQ (Davide Caratti)
- redhat: ark: disable CONFIG_NET_SCH_PLUG (Davide Caratti)
- redhat: ark: disable CONFIG_NET_SCH_PIE (Davide Caratti)
- redhat: ark: disable CONFIG_NET_SCH_HHF (Davide Caratti)
- redhat: ark: disable CONFIG_NET_SCH_DSMARK (Davide Caratti)
- redhat: ark: disable CONFIG_NET_SCH_DRR (Davide Caratti)
- redhat: ark: disable CONFIG_NET_SCH_CODEL (Davide Caratti)
- redhat: ark: disable CONFIG_NET_SCH_CHOKE (Davide Caratti)
- redhat: ark: disable CONFIG_NET_SCH_CBQ (Davide Caratti)
- redhat: ark: disable CONFIG_NET_SCH_ATM (Davide Caratti)
- redhat: ark: disable CONFIG_NET_EMATCH and sub-targets (Davide Caratti)
- redhat: ark: disable CONFIG_NET_CLS_TCINDEX (Davide Caratti)
- redhat: ark: disable CONFIG_NET_CLS_RSVP6 (Davide Caratti)
- redhat: ark: disable CONFIG_NET_CLS_RSVP (Davide Caratti)
- redhat: ark: disable CONFIG_NET_CLS_ROUTE4 (Davide Caratti)
- redhat: ark: disable CONFIG_NET_CLS_BASIC (Davide Caratti)
- redhat: ark: disable CONFIG_NET_ACT_SKBMOD (Davide Caratti)
- redhat: ark: disable CONFIG_NET_ACT_SIMP (Davide Caratti)
- redhat: ark: disable CONFIG_NET_ACT_NAT (Davide Caratti)
- arm64/defconfig: Enable CONFIG_KEXEC_FILE (Bhupesh Sharma) [1821565]
- redhat/configs: Cleanup CONFIG_CRYPTO_SHA512 (Prarit Bhargava)
- New configs in drivers/mfd (Fedora Kernel Team)
- Fix LTO issues with kernel-tools (Don Zickus)
- Point pathfix to the new location for gen_compile_commands.py (Justin M. Forbes)
- configs: Disable CONFIG_SECURITY_SELINUX_DISABLE (Ondrej Mosnacek)
- [Automatic] Handle config dependency changes (Don Zickus)
- configs/iommu: Add config comment to empty CONFIG_SUN50I_IOMMU file (Jerry Snitselaar)
- New configs in kernel/trace (Fedora Kernel Team)
- Fix Fedora config locations (Justin M. Forbes)
- Fedora config updates (Justin M. Forbes)
- configs: enable CONFIG_CRYPTO_CTS=y so cts(cbc(aes)) is available in FIPS mode (Vladis Dronov) [1855161]
- Partial revert: Add master merge check (Don Zickus)
- Update Maintainers doc to reflect workflow changes (Don Zickus)
- WIP: redhat/docs: Update documentation for single branch workflow (Prarit Bhargava)
- Add CONFIG_ARM64_MTE which is not picked up by the config scripts for some reason (Justin M. Forbes)
- Disable Speakup synth DECEXT (Justin M. Forbes)
- Enable Speakup for Fedora since it is out of staging (Justin M. Forbes)
- Modify patchlist changelog output (Don Zickus)
- process_configs.sh: Fix syntax flagged by shellcheck (Ben Crocker)
- generate_all_configs.sh: Fix syntax flagged by shellcheck (Ben Crocker)
- redhat/self-test: Initial commit (Ben Crocker)
- arch/x86: Remove vendor specific CPU ID checks (Prarit Bhargava)
- redhat: Replace hardware.redhat.com link in Unsupported message (Prarit Bhargava) [1810301]
- x86: Fix compile issues with rh_check_supported() (Don Zickus)
- KEYS: Make use of platform keyring for module signature verify (Robert Holmes)
- Input: rmi4 - remove the need for artificial IRQ in case of HID (Benjamin Tissoires)
- ARM: tegra: usb no reset (Peter Robinson)
- arm: make CONFIG_HIGHPTE optional without CONFIG_EXPERT (Jon Masters)
- redhat: rh_kabi: deduplication friendly structs (Jiri Benc)
- redhat: rh_kabi add a comment with warning about RH_KABI_EXCLUDE usage (Jiri Benc)
- redhat: rh_kabi: introduce RH_KABI_EXTEND_WITH_SIZE (Jiri Benc)
- redhat: rh_kabi: Indirect EXTEND macros so nesting of other macros will resolve. (Don Dutile)
- redhat: rh_kabi: Fix RH_KABI_SET_SIZE to use dereference operator (Tony Camuso)
- redhat: rh_kabi: Add macros to size and extend structs (Prarit Bhargava)
- Removing Obsolete hba pci-ids from rhel8 (Dick Kennedy) [1572321]
- mptsas: pci-id table changes (Laura Abbott)
- mptsas: Taint kernel if mptsas is loaded (Laura Abbott)
- mptspi: pci-id table changes (Laura Abbott)
- qla2xxx: Remove PCI IDs of deprecated adapter (Jeremy Cline)
- be2iscsi: remove unsupported device IDs (Chris Leech) [1574502 1598366]
- mptspi: Taint kernel if mptspi is loaded (Laura Abbott)
- hpsa: remove old cciss-based smartarray pci ids (Joseph Szczypek) [1471185]
- qla4xxx: Remove deprecated PCI IDs from RHEL 8 (Chad Dupuis) [1518874]
- aacraid: Remove depreciated device and vendor PCI id's (Raghava Aditya Renukunta) [1495307]
- megaraid_sas: remove deprecated pci-ids (Tomas Henzl) [1509329]
- mpt*: remove certain deprecated pci-ids (Jeremy Cline)
- kernel: add SUPPORT_REMOVED kernel taint (Tomas Henzl) [1602033]
- Rename RH_DISABLE_DEPRECATED to RHEL_DIFFERENCES (Don Zickus)
- s390: Lock down the kernel when the IPL secure flag is set (Jeremy Cline)
- efi: Lock down the kernel if booted in secure boot mode (David Howells)
- efi: Add an EFI_SECURE_BOOT flag to indicate secure boot mode (David Howells)
- security: lockdown: expose a hook to lock the kernel down (Jeremy Cline)
- Make get_cert_list() use efi_status_to_str() to print error messages. (Peter Jones)
- Add efi_status_to_str() and rework efi_status_to_err(). (Peter Jones)
- Add support for deprecating processors (Laura Abbott) [1565717 1595918 1609604 1610493]
- arm: aarch64: Drop the EXPERT setting from ARM64_FORCE_52BIT (Jeremy Cline)
- iommu/arm-smmu: workaround DMA mode issues (Laura Abbott)
- rh_kabi: introduce RH_KABI_EXCLUDE (Jakub Racek) [1652256]
- ipmi: do not configure ipmi for HPE m400 (Laura Abbott) [1670017]
- kABI: Add generic kABI macros to use for kABI workarounds (Myron Stowe) [1546831]
- add pci_hw_vendor_status() (Maurizio Lombardi) [1590829]
- ahci: thunderx2: Fix for errata that affects stop engine (Robert Richter) [1563590]
- Vulcan: AHCI PCI bar fix for Broadcom Vulcan early silicon (Robert Richter) [1563590]
- bpf: set unprivileged_bpf_disabled to 1 by default, add a boot parameter (Eugene Syromiatnikov) [1561171]
- add Red Hat-specific taint flags (Eugene Syromiatnikov) [1559877]
- tags.sh: Ignore redhat/rpm (Jeremy Cline)
- put RHEL info into generated headers (Laura Abbott) [1663728]
- aarch64: acpi scan: Fix regression related to X-Gene UARTs (Mark Salter) [1519554]
- ACPI / irq: Workaround firmware issue on X-Gene based m400 (Mark Salter) [1519554]
- modules: add rhelversion MODULE_INFO tag (Laura Abbott)
- ACPI: APEI: arm64: Ignore broken HPE moonshot APEI support (Al Stone) [1518076]
- Add Red Hat tainting (Laura Abbott) [1565704 1652266]
- Introduce CONFIG_RH_DISABLE_DEPRECATED (Laura Abbott)
- Stop merging ark-patches for release (Don Zickus)
- Fix path location for ark-update-configs.sh (Don Zickus)
- Combine Red Hat patches into single patch (Don Zickus)
- New configs in drivers/misc (Jeremy Cline)
- New configs in drivers/net/wireless (Justin M. Forbes)
- New configs in drivers/phy (Fedora Kernel Team)
- New configs in drivers/tty (Fedora Kernel Team)
- Set SquashFS decompression options for all flavors to match RHEL (Bohdan Khomutskyi)
- configs: Enable CONFIG_ENERGY_MODEL (Phil Auld)
- New configs in drivers/pinctrl (Fedora Kernel Team)
- Update CONFIG_THERMAL_NETLINK (Justin Forbes)
- Separate merge-upstream and release stages (Don Zickus)
- Re-enable CONFIG_IR_SERIAL on Fedora (Prarit Bhargava)
- Create Patchlist.changelog file (Don Zickus)
- Filter out upstream commits from changelog (Don Zickus)
- Merge Upstream script fixes (Don Zickus)
- kernel.spec: Remove kernel-keys directory on rpm erase (Prarit Bhargava)
- Add mlx5_vdpa to module filter for Fedora (Justin M. Forbes)
- Add python3-sphinx_rtd_theme buildreq for docs (Justin M. Forbes)
- redhat/configs/process_configs.sh: Remove *.config.orig files (Prarit Bhargava)
- redhat/configs/process_configs.sh: Add process_configs_known_broken flag (Prarit Bhargava)
- redhat/Makefile: Fix '*-configs' targets (Prarit Bhargava)
- dist-merge-upstream: Checkout known branch for ci scripts (Don Zickus)
- kernel.spec: don't override upstream compiler flags for ppc64le (Dan Horák)
- Fedora config updates (Justin M. Forbes)
- Fedora confi gupdate (Justin M. Forbes)
- mod-sign.sh: Fix syntax flagged by shellcheck (Ben Crocker)
- Swap how ark-latest is built (Don Zickus)
- Add extra version bump to os-build branch (Don Zickus)
- dist-release: Avoid needless version bump. (Don Zickus)
- Add dist-fedora-release target (Don Zickus)
- Remove redundant code in dist-release (Don Zickus)
- Makefile.common rename TAG to _TAG (Don Zickus)
- Fedora config change (Justin M. Forbes)
- Fedora filter update (Justin M. Forbes)
- Config update for Fedora (Justin M. Forbes)
- enable PROTECTED_VIRTUALIZATION_GUEST for all s390x kernels (Dan Horák)
- redhat: ark: enable CONFIG_NET_SCH_TAPRIO (Davide Caratti)
- redhat: ark: enable CONFIG_NET_SCH_ETF (Davide Caratti)
- More Fedora config updates (Justin M. Forbes)
- New config deps (Justin M. Forbes)
- Fedora config updates (Justin M. Forbes)
- First half of config updates for Fedora (Justin M. Forbes)
- Updates for Fedora arm architectures for the 5.9 window (Peter Robinson)
- Merge 5.9 config changes from Peter Robinson (Justin M. Forbes)
- Add config options that only show up when we prep on arm (Justin M. Forbes)
- Config updates for Fedora (Justin M. Forbes)
- fedora: enable enery model (Peter Robinson)
- Use the configs/generic config for SND_HDA_INTEL everywhere (Peter Robinson)
- Enable ZSTD compression algorithm on all kernels (Peter Robinson)
- Enable ARM_SMCCC_SOC_ID on all aarch64 kernels (Peter Robinson)
- iio: enable LTR-559 light and proximity sensor (Peter Robinson)
- iio: chemical: enable some popular chemical and partical sensors (Peter Robinson)
- More mismatches (Justin M. Forbes)
- Fedora config change due to deps (Justin M. Forbes)
- CONFIG_SND_SOC_MAX98390 is now selected by SND_SOC_INTEL_DA7219_MAX98357A_GENERIC (Justin M. Forbes)
- Config change required for build part 2 (Justin M. Forbes)
- Config change required for build (Justin M. Forbes)
- Fedora config update (Justin M. Forbes)
- Add ability to sync upstream through Makefile (Don Zickus)
- Add master merge check (Don Zickus)
- Replace hardcoded values 'os-build' and project id with variables (Don Zickus)
- redhat/Makefile.common: Fix MARKER (Prarit Bhargava)
- gitattributes: Remove unnecesary export restrictions (Prarit Bhargava)
- Add new certs for dual signing with boothole (Justin M. Forbes)
- Update secureboot signing for dual keys (Justin M. Forbes)
- fedora: enable LEDS_SGM3140 for arm configs (Peter Robinson)
- Enable CONFIG_DM_VERITY_VERIFY_ROOTHASH_SIG (Justin M. Forbes)
- redhat/configs: Fix common CONFIGs (Prarit Bhargava)
- redhat/configs: General CONFIG cleanups (Prarit Bhargava)
- redhat/configs: Update & generalize evaluate_configs (Prarit Bhargava)
- fedora: arm: Update some meson config options (Peter Robinson)
- redhat/docs: Add Fedora RPM tagging date (Prarit Bhargava)
- Update config for renamed panel driver. (Peter Robinson)
- Enable SERIAL_SC16IS7XX for SPI interfaces (Peter Robinson)
- s390x-zfcpdump: Handle missing Module.symvers file (Don Zickus)
- Fedora config updates (Justin M. Forbes)
- redhat/configs: Add .tmp files to .gitignore (Prarit Bhargava)
- disable uncommon TCP congestion control algorithms (Davide Caratti)
- Add new bpf man pages (Justin M. Forbes)
- Add default option for CONFIG_ARM64_BTI_KERNEL to pending-common so that eln kernels build (Justin M. Forbes)
- redhat/Makefile: Add fedora-configs and rh-configs make targets (Prarit Bhargava)
- redhat/configs: Use SHA512 for module signing (Prarit Bhargava)
- genspec.sh: 'touch' empty Patchlist file for single tarball (Don Zickus)
- Fedora config update for rc1 (Justin M. Forbes)
- Fedora config updates (Justin M. Forbes)
- Fedora config updates (Justin M. Forbes)
- redhat/Makefile.common: fix RPMKSUBLEVEL condition (Ondrej Mosnacek)
- redhat/Makefile: silence KABI tar output (Ondrej Mosnacek)
- One more Fedora config update (Justin M. Forbes)
- Fedora config updates (Justin M. Forbes)
- Fix PATCHLEVEL for merge window (Justin M. Forbes)
- Change ark CONFIG_COMMON_CLK to yes, it is selected already by other options (Justin M. Forbes)
- Fedora config updates (Justin M. Forbes)
- Fedora config updates (Justin M. Forbes)
- Fedora config updates (Justin M. Forbes)
- More module filtering for Fedora (Justin M. Forbes)
- Update filters for rnbd in Fedora (Justin M. Forbes)
- Fedora config updates (Justin M. Forbes)
- Fix up module filtering for 5.8 (Justin M. Forbes)
- Fedora config updates (Justin M. Forbes)
- More Fedora config work (Justin M. Forbes)
- RTW88BE and CE have been extracted to their own modules (Justin M. Forbes)
- Set CONFIG_BLK_INLINE_ENCRYPTION_FALLBACK for Fedora (Justin M. Forbes)
- Fedora config updates (Justin M. Forbes)
- Arm64 Use Branch Target Identification for kernel (Justin M. Forbes)
- Change value of CONFIG_SECURITY_SELINUX_CHECKREQPROT_VALUE (Justin M. Forbes)
- Fedora config updates (Justin M. Forbes)
- Fix configs for Fedora (Justin M. Forbes)
- Add zero-commit to format-patch options (Justin M. Forbes)
- Copy Makefile.rhelver as a source file rather than a patch (Jeremy Cline)
- Move the sed to clear the patch templating outside of conditionals (Justin M. Forbes)
- Match template format in kernel.spec.template (Justin M. Forbes)
- Break out the Patches into individual files for dist-git (Justin M. Forbes)
- Break the Red Hat patch into individual commits (Jeremy Cline)
- Fix update_scripts.sh unselective pattern sub (David Howells)
- Add cec to the filter overrides (Justin M. Forbes)
- Add overrides to filter-modules.sh (Justin M. Forbes)
- redhat/configs: Enable CONFIG_SMC91X and disable CONFIG_SMC911X (Prarit Bhargava) [1722136]
- Include bpftool-struct_ops man page in the bpftool package (Jeremy Cline)
- Add sharedbuffer_configuration.py to the pathfix.py script (Jeremy Cline)
- Use __make macro instead of make (Tom Stellard)
- Sign off generated configuration patches (Jeremy Cline)
- Drop the static path configuration for the Sphinx docs (Jeremy Cline)
- redhat: Add dummy-module kernel module (Prarit Bhargava)
- redhat: enable CONFIG_LWTUNNEL_BPF (Jiri Benc)
- Remove typoed config file aarch64CONFIG_SM_GCC_8150 (Justin M. Forbes)
- Add Documentation back to kernel-devel as it has Kconfig now (Justin M. Forbes)
- Copy distro files rather than moving them (Jeremy Cline)
- kernel.spec: fix 'make scripts' for kernel-devel package (Brian Masney)
- Makefile: correct help text for dist-cross-<arch>-rpms (Brian Masney)
- redhat/Makefile: Fix RHEL8 python warning (Prarit Bhargava)
- redhat: Change Makefile target names to dist- (Prarit Bhargava)
- configs: Disable Serial IR driver (Prarit Bhargava)
- Fix "multiple %%files for package kernel-tools" (Pablo Greco)
- Introduce a Sphinx documentation project (Jeremy Cline)
- Build ARK against ELN (Don Zickus)
- Drop the requirement to have a remote called linus (Jeremy Cline)
- Rename 'internal' branch to 'os-build' (Don Zickus)
- Only include open merge requests with "Include in Releases" label (Jeremy Cline)
- Package gpio-watch in kernel-tools (Jeremy Cline)
- Exit non-zero if the tag already exists for a release (Jeremy Cline)
- Adjust the changelog update script to not push anything (Jeremy Cline)
- Drop --target noarch from the rh-rpms make target (Jeremy Cline)
- Add a script to generate release tags and branches (Jeremy Cline)
- Set CONFIG_VDPA for fedora (Justin M. Forbes)
- Add a README to the dist-git repository (Jeremy Cline)
- Provide defaults in ark-rebase-patches.sh (Jeremy Cline)
- Default ark-rebase-patches.sh to not report issues (Jeremy Cline)
- Drop DIST from release commits and tags (Jeremy Cline)
- Place the buildid before the dist in the release (Jeremy Cline)
- Sync up with Fedora arm configuration prior to merging (Jeremy Cline)
- Disable CONFIG_PROTECTED_VIRTUALIZATION_GUEST for zfcpdump (Jeremy Cline)
- Add RHMAINTAINERS file and supporting conf (Don Zickus)
- Add a script to test if all commits are signed off (Jeremy Cline)
- Fix make rh-configs-arch (Don Zickus)
- Drop RH_FEDORA in favor of the now-merged RHEL_DIFFERENCES (Jeremy Cline)
- Sync up Fedora configs from the first week of the merge window (Jeremy Cline)
- Migrate blacklisting floppy.ko to mod-blacklist.sh (Don Zickus)
- kernel packaging: Combine mod-blacklist.sh and mod-extra-blacklist.sh (Don Zickus)
- kernel packaging: Fix extra namespace collision (Don Zickus)
- mod-extra.sh: Rename to mod-blacklist.sh (Don Zickus)
- mod-extra.sh: Make file generic (Don Zickus)
- Fix a painfully obvious YAML syntax error in .gitlab-ci.yml (Jeremy Cline)
- Add in armv7hl kernel header support (Don Zickus)
- Disable all BuildKernel commands when only building headers (Don Zickus)
- Drop any gitlab-ci patches from ark-patches (Jeremy Cline)
- Build the srpm for internal branch CI using the vanilla tree (Jeremy Cline)
- Pull in the latest ARM configurations for Fedora (Jeremy Cline)
- Fix xz memory usage issue (Neil Horman)
- Use ark-latest instead of master for update script (Jeremy Cline)
- Move the CI jobs back into the ARK repository (Jeremy Cline)
- Sync up ARK's Fedora config with the dist-git repository (Jeremy Cline)
- Pull in the latest configuration changes from Fedora (Jeremy Cline)
- configs: enable CONFIG_NET_SCH_CBS (Marcelo Ricardo Leitner)
- Drop configuration options in fedora/ that no longer exist (Jeremy Cline)
- Set RH_FEDORA for ARK and Fedora (Jeremy Cline)
- redhat/kernel.spec: Include the release in the kernel COPYING file (Jeremy Cline)
- redhat/kernel.spec: add scripts/jobserver-exec to py3_shbang_opts list (Jeremy Cline)
- redhat/kernel.spec: package bpftool-gen man page (Jeremy Cline)
- distgit-changelog: handle multiple y-stream BZ numbers (Bruno Meneguele)
- redhat/kernel.spec: remove all inline comments (Bruno Meneguele)
- redhat/genspec: awk unknown whitespace regex pattern (Bruno Meneguele)
- Improve the readability of gen_config_patches.sh (Jeremy Cline)
- Fix some awkward edge cases in gen_config_patches.sh (Jeremy Cline)
- Update the CI environment to use Fedora 31 (Jeremy Cline)
- redhat: drop whitespace from with_gcov macro (Jan Stancek)
- configs: Enable CONFIG_KEY_DH_OPERATIONS on ARK (Ondrej Mosnacek)
- configs: Adjust CONFIG_MPLS_ROUTING and CONFIG_MPLS_IPTUNNEL (Laura Abbott)
- New configs in lib/crypto (Jeremy Cline)
- New configs in drivers/char (Jeremy Cline)
- Turn on BLAKE2B for Fedora (Jeremy Cline)
- kernel.spec.template: Clean up stray *.h.s files (Laura Abbott)
- Build the SRPM in the CI job (Jeremy Cline)
- New configs in net/tls (Jeremy Cline)
- New configs in net/tipc (Jeremy Cline)
- New configs in lib/kunit (Jeremy Cline)
- Fix up released_kernel case (Laura Abbott)
- New configs in lib/Kconfig.debug (Jeremy Cline)
- New configs in drivers/ptp (Jeremy Cline)
- New configs in drivers/nvme (Jeremy Cline)
- New configs in drivers/net/phy (Jeremy Cline)
- New configs in arch/arm64 (Jeremy Cline)
- New configs in drivers/crypto (Jeremy Cline)
- New configs in crypto/Kconfig (Jeremy Cline)
- Add label so the Gitlab to email bridge ignores the changelog (Jeremy Cline)
- Temporarily switch TUNE_DEFAULT to y (Jeremy Cline)
- Run config test for merge requests and internal (Jeremy Cline)
- Add missing licensedir line (Laura Abbott)
- redhat/scripts: Remove redhat/scripts/rh_get_maintainer.pl (Prarit Bhargava)
- configs: Take CONFIG_DEFAULT_MMAP_MIN_ADDR from Fedra (Laura Abbott)
- configs: Turn off ISDN (Laura Abbott)
- Add a script to generate configuration patches (Laura Abbott)
- Introduce rh-configs-commit (Laura Abbott)
- kernel-packaging: Remove kernel files from kernel-modules-extra package (Prarit Bhargava)
- configs: Enable CONFIG_DEBUG_WX (Laura Abbott)
- configs: Disable wireless USB (Laura Abbott)
- Clean up some temporary config files (Laura Abbott)
- configs: New config in drivers/gpu for v5.4-rc1 (Jeremy Cline)
- configs: New config in arch/powerpc for v5.4-rc1 (Jeremy Cline)
- configs: New config in crypto for v5.4-rc1 (Jeremy Cline)
- configs: New config in drivers/usb for v5.4-rc1 (Jeremy Cline)
- AUTOMATIC: New configs (Jeremy Cline)
- Skip ksamples for bpf, they are broken (Jeremy Cline)
- configs: New config in fs/erofs for v5.4-rc1 (Jeremy Cline)
- configs: New config in mm for v5.4-rc1 (Jeremy Cline)
- configs: New config in drivers/md for v5.4-rc1 (Jeremy Cline)
- configs: New config in init for v5.4-rc1 (Jeremy Cline)
- configs: New config in fs/fuse for v5.4-rc1 (Jeremy Cline)
- merge.pl: Avoid comments but do not skip them (Don Zickus)
- configs: New config in drivers/net/ethernet/pensando for v5.4-rc1 (Jeremy Cline)
- Update a comment about what released kernel means (Laura Abbott)
- Provide both Fedora and RHEL files in the SRPM (Laura Abbott)
- kernel.spec.template: Trim EXTRAVERSION in the Makefile (Laura Abbott)
- kernel.spec.template: Add macros for building with nopatches (Laura Abbott)
- kernel.spec.template: Add some macros for Fedora differences (Laura Abbott)
- kernel.spec.template: Consolodate the options (Laura Abbott)
- configs: Add pending direcory to Fedora (Laura Abbott)
- kernel.spec.template: Don't run hardlink if rpm-ostree is in use (Laura Abbott)
- configs: New config in net/can for v5.4-rc1 (Jeremy Cline)
- configs: New config in drivers/net/phy for v5.4-rc1 (Jeremy Cline)
- configs: Increase x86_64 NR_UARTS to 64 (Prarit Bhargava) [1730649]
- configs: turn on ARM64_FORCE_52BIT for debug builds (Jeremy Cline)
- kernel.spec.template: Tweak the python3 mangling (Laura Abbott)
- kernel.spec.template: Add --with verbose option (Laura Abbott)
- kernel.spec.template: Switch to using %%install instead of %%__install (Laura Abbott)
- kernel.spec.template: Make the kernel.org URL https (Laura Abbott)
- kernel.spec.template: Update message about secure boot signing (Laura Abbott)
- kernel.spec.template: Move some with flags definitions up (Laura Abbott)
- kernel.spec.template: Update some BuildRequires (Laura Abbott)
- kernel.spec.template: Get rid of %%clean (Laura Abbott)
- configs: New config in drivers/char for v5.4-rc1 (Jeremy Cline)
- configs: New config in net/sched for v5.4-rc1 (Jeremy Cline)
- configs: New config in lib for v5.4-rc1 (Jeremy Cline)
- configs: New config in fs/verity for v5.4-rc1 (Jeremy Cline)
- configs: New config in arch/aarch64 for v5.4-rc4 (Jeremy Cline)
- configs: New config in arch/arm64 for v5.4-rc1 (Jeremy Cline)
- Flip off CONFIG_ARM64_VA_BITS_52 so the bundle that turns it on applies (Jeremy Cline)
- New configuration options for v5.4-rc4 (Jeremy Cline)
- Correctly name tarball for single tarball builds (Laura Abbott)
- configs: New config in drivers/pci for v5.4-rc1 (Jeremy Cline)
- Allow overriding the dist tag on the command line (Laura Abbott)
- Allow scratch branch target to be overridden (Laura Abbott)
- Remove long dead BUILD_DEFAULT_TARGET (Laura Abbott)
- Amend the changelog when rebasing (Laura Abbott)
- configs: New config in drivers/platform for v5.4-rc1 (Jeremy Cline)
- configs: New config in drivers/pinctrl for v5.4-rc1 (Jeremy Cline)
- configs: New config in drivers/net/wireless for v5.4-rc1 (Jeremy Cline)
- configs: New config in drivers/net/ethernet/mellanox for v5.4-rc1 (Jeremy Cline)
- configs: New config in drivers/net/can for v5.4-rc1 (Jeremy Cline)
- configs: New config in drivers/hid for v5.4-rc1 (Jeremy Cline)
- configs: New config in drivers/dma-buf for v5.4-rc1 (Jeremy Cline)
- configs: New config in drivers/crypto for v5.4-rc1 (Jeremy Cline)
- configs: New config in arch/s390 for v5.4-rc1 (Jeremy Cline)
- configs: New config in block for v5.4-rc1 (Jeremy Cline)
- configs: New config in drivers/cpuidle for v5.4-rc1 (Jeremy Cline)
- redhat: configs: Split CONFIG_CRYPTO_SHA512 (Laura Abbott)
- redhat: Set Fedora options (Laura Abbott)
- Set CRYPTO_SHA3_*_S390 to builtin on zfcpdump (Jeremy Cline)
- configs: New config in drivers/edac for v5.4-rc1 (Jeremy Cline)
- configs: New config in drivers/firmware for v5.4-rc1 (Jeremy Cline)
- configs: New config in drivers/hwmon for v5.4-rc1 (Jeremy Cline)
- configs: New config in drivers/iio for v5.4-rc1 (Jeremy Cline)
- configs: New config in drivers/mmc for v5.4-rc1 (Jeremy Cline)
- configs: New config in drivers/tty for v5.4-rc1 (Jeremy Cline)
- configs: New config in arch/s390 for v5.4-rc1 (Jeremy Cline)
- configs: New config in drivers/bus for v5.4-rc1 (Jeremy Cline)
- Add option to allow mismatched configs on the command line (Laura Abbott)
- configs: New config in drivers/crypto for v5.4-rc1 (Jeremy Cline)
- configs: New config in sound/pci for v5.4-rc1 (Jeremy Cline)
- configs: New config in sound/soc for v5.4-rc1 (Jeremy Cline)
- gitlab: Add CI job for packaging scripts (Major Hayden)
- Speed up CI with CKI image (Major Hayden)
- Disable e1000 driver in ARK (Neil Horman)
- configs: Fix the pending default for CONFIG_ARM64_VA_BITS_52 (Jeremy Cline)
- configs: Turn on OPTIMIZE_INLINING for everything (Jeremy Cline)
- configs: Set valid pending defaults for CRYPTO_ESSIV (Jeremy Cline)
- Add an initial CI configuration for the internal branch (Jeremy Cline)
- New drop of configuration options for v5.4-rc1 (Jeremy Cline)
- New drop of configuration options for v5.4-rc1 (Jeremy Cline)
- Pull the RHEL version defines out of the Makefile (Jeremy Cline)
- Sync up the ARK build scripts (Jeremy Cline)
- Sync up the Fedora Rawhide configs (Jeremy Cline)
- Sync up the ARK config files (Jeremy Cline)
- configs: Adjust CONFIG_FORCE_MAX_ZONEORDER for Fedora (Laura Abbott)
- configs: Add README for some other arches (Laura Abbott)
- configs: Sync up Fedora configs (Laura Abbott)
- [initial commit] Add structure for building with git (Laura Abbott)
- [initial commit] Add Red Hat variables in the top level makefile (Laura Abbott)
- [initial commit] Red Hat gitignore and attributes (Laura Abbott)
- [initial commit] Add changelog (Laura Abbott)
- [initial commit] Add makefile (Laura Abbott)
- [initial commit] Add files for generating the kernel.spec (Laura Abbott)
- [initial commit] Add rpm directory (Laura Abbott)
- [initial commit] Add files for packaging (Laura Abbott)
- [initial commit] Add kabi files (Laura Abbott)
- [initial commit] Add scripts (Laura Abbott)
- [initial commit] Add configs (Laura Abbott)
- [initial commit] Add Makefiles (Laura Abbott)
- Linux v6.6.0-0.rc0.1c59d383390f

###
# The following Emacs magic makes C-c C-e use UTC dates.
# Local Variables:
# rpm-change-log-uses-utc: t
# End:
###
