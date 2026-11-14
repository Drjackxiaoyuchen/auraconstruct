"""Install the pinned, separate annotation engine and checksum-verified database bundle."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

from auraconstruct.engine import environment,status
from auraconstruct.library import data_dir


def run(args,env=None):
    subprocess.run([str(a) for a in args],env=env,check=True)


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    root=data_dir();prefix=root/'plannotate-env';exe=prefix/'bin/plannotate'
    if not exe.exists():
        manager=next((shutil.which(m) for m in ('mamba','micromamba','conda') if shutil.which(m)),None)
        if not manager:raise SystemExit('Install mamba, micromamba or conda, then rerun this setup.')
        run([manager,'create','--prefix',prefix,'--override-channels','-c','conda-forge','-c','bioconda',
             'python=3.11','plannotate=2.0.0','--yes'])
    env=environment(exe)
    check=status()
    if check['ready']:
        print(json.dumps(check,indent=2));return
    curl=shutil.which('curl')
    if not curl:raise SystemExit('Install curl to download and verify the database bundle.')
    downloads=root/'downloads';downloads.mkdir(parents=True,exist_ok=True)
    base='https://github.com/mmcguffi/pLannotate/releases/download/v2.0.0/'
    archive=downloads/'plannotate-databases-v2.tar.gz';checksum=downloads/(archive.name+'.sha256')
    def fetch(name,target):
        run([curl,'--fail','--location','--connect-timeout','20','--max-time','600','--retry','2',
             '--retry-delay','2','--output',target,base+name+'?download=1'])
    if not checksum.exists():fetch(checksum.name,checksum)
    expected=checksum.read_text().split()[0]
    if not archive.exists() or digest(archive)!=expected:
        partial=archive.with_suffix('.partial');fetch(archive.name,partial)
        if digest(partial)!=expected:raise SystemExit('Database archive checksum mismatch; installation stopped.')
        partial.replace(archive)
    env.update(PLANNOTATE_DATABASE_URL=archive.as_uri(),PLANNOTATE_DATABASE_SHA256=expected)
    run([prefix/'bin/python','-c','from plannotate import _package_data; _package_data.download_databases()'],env)
    (downloads/'plannotate-databases-v2.provenance.json').write_text(json.dumps(
        {'url':base+archive.name,'sha256':expected,'size':archive.stat().st_size},indent=2))
    check=status();print(json.dumps(check,indent=2))
    if not check['ready']:raise SystemExit(1)


if __name__=='__main__':main()
