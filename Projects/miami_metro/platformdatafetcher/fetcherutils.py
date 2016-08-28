import baker
import subprocess
import logging

from xpathscraper import utils


log = logging.getLogger('platformdatafetcher.fetcherutils')


@baker.command
def spawn_update_blogs_from_xpaths(from_num='1', to_num='202', num_procs='10'):
    procs = []
    all = range(int(from_num), int(to_num)+1)
    for (start, end) in utils.chunk_ranges(all, len(all) // int(num_procs)):
        cmd = 'python -m debra.script_dispatcher %s %s > update_blogs_from_xpaths_%s_%s.log 2>&1' % (start, end, start, end)
        log.warn('spawning "%s"' % cmd)
        p = subprocess.Popen(cmd, shell=True)
        procs.append(p)
    for p in procs:
        p.wait()
    log.warn('finished spawn_update_blogs_from_xpaths')


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
