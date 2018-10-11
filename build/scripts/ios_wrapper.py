import os
import shutil
import subprocess
import sys
import tarfile
import plistlib


def ensure_dir(path):
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST or not os.path.isdir(path):
            raise


def just_do_it(args):
    if not args:
        raise Exception('Not enough args!')
    parts = [[]]
    for arg in args:
        if arg == '__DELIM__':
            parts.append([])
        else:
            parts[-1].append(arg)
    if len(parts) != 4 or len(parts[0]) != 3:
        raise Exception('Bad call')
    main_out, app_name, module_dir = parts[0]
    inputs, binaries, storyboard_user_flags = parts[1:]
    plists, storyboards, signs, nibs = [], [], [], []
    for i in inputs:
        if i.endswith('.plist') or i.endswith('.partial_plist'):
            plists.append(i)
        elif i.endswith('.compiled_storyboard_tar'):
            storyboards.append(i)
        elif i.endswith('.xcent'):
            signs.append(i)
        elif i.endswith('.nib'):
            nibs.append(i)
        else:
            print >> sys.stderr, 'Unknown input:', i, 'ignoring'
    if not plists:
        raise Exception("Can't find plist files")
    if not plists[0].endswith('.plist'):
        print >> sys.stderr, "Main plist file can be defined incorretly"
    if not storyboards:
        print >> sys.stderr, "Storyboards list are empty"
    if len(signs) > 1:
        raise Exception("Too many .xcent files")
    if not len(binaries):
        print >> sys.stderr, "No binary files found in your application"
    main_binary = None
    for binary in binaries:
        if is_exe(binary):
            if main_binary is not None:
                print >> sys.stderr, "Multiple executable files found in your application,", main_binary, "will be used"
            else:
                main_binary = binary
    if not main_binary:
        print >> sys.stderr, "No executable file found in your application, check PEERDIR section"
    app_dir = os.path.join(module_dir, app_name + '.app')
    ensure_dir(app_dir)
    copy_nibs(nibs, module_dir, app_dir)
    replaced_parameters = {
        '$(DEVELOPMENT_LANGUAGE)': 'en',
        '$(EXECUTABLE_NAME)': os.path.basename(main_binary) if main_binary else '',
        '$(PRODUCT_BUNDLE_IDENTIFIER)': 'Yandex.' + app_name,
        '$(PRODUCT_NAME)': app_name,
    }
    make_main_plist(plists, os.path.join(app_dir, 'Info.plist'), replaced_parameters)
    link_storyboards(storyboards, app_name, app_dir, storyboard_user_flags)
    if not signs:
        sign_file = os.path.join(module_dir, app_name + '.xcent')
        with open(sign_file, 'w') as f:
            f.write('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
        <key>com.apple.security.get-task-allow</key>
        <true/>
</dict>
</plist>
            ''')
    else:
        sign_file = signs[0]
    sign_application(sign_file, app_dir)
    for b in binaries:
        shutil.copy(b, os.path.join(app_dir, os.path.basename(b)))
    make_archive(app_dir, main_out)


def is_exe(fpath):
    return os.path.isfile(fpath) and os.access(fpath, os.X_OK)


def copy_nibs(nibs, module_dir, app_dir):
    for nib in nibs:
        dst = os.path.join(app_dir, os.path.relpath(nib, module_dir))
        ensure_dir(os.path.dirname(dst))
        shutil.copyfile(nib, dst)


def make_main_plist(inputs, out, replaced_parameters):
    united_data = {}
    for i in inputs:
        united_data.update(plistlib.readPlist(i))

    def scan_n_replace(root):
        if not isinstance(root, dict):
            raise Exception('Invalid state')
        for k in root:
            if isinstance(root[k], list):
                for i in xrange(len(root[k])):
                    if isinstance(root[k][i], dict):
                        scan_n_replace(root[k][i])
                    elif root[k][i] in replaced_parameters:
                        root[k][i] = replaced_parameters[root[k][i]]
            elif isinstance(root[k], dict):
                scan_n_replace(root[k])
            else:
                if root[k] in replaced_parameters:
                    root[k] = replaced_parameters[root[k]]
    scan_n_replace(united_data)
    plistlib.writePlist(united_data, out)
    subprocess.check_call(['plutil', '-convert', 'binary1', out])


def link_storyboards(archives, app_name, app_dir, flags):
    unpacked = []
    for arc in archives:
        unpacked.append(os.path.splitext(arc)[0] + 'c')
        ensure_dir(unpacked[-1])
        with tarfile.open(arc) as a:
            a.extractall(path=unpacked[-1])
    flags += [
        '--module', app_name,
        '--link', app_dir,
    ]
    subprocess.check_call(['/usr/bin/xcrun', 'ibtool'] + flags +
                          ['--errors', '--warnings', '--notices', '--output-format', 'human-readable-text'] +
                          unpacked)


def sign_application(xcent, app_dir):
    subprocess.check_call(['/usr/bin/codesign', '--force', '--sign', '-', '--entitlements', xcent, '--timestamp=none', app_dir])


def make_archive(app_dir, output):
    with tarfile.open(output, "w") as tar_handle:
        for root, _, files in os.walk(app_dir):
            for f in files:
                tar_handle.add(os.path.join(root, f), arcname=os.path.join(os.path.basename(app_dir),
                                                                           os.path.relpath(os.path.join(root, f), app_dir)))


if __name__ == '__main__':
    just_do_it(sys.argv[1:])
