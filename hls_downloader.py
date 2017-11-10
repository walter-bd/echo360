#coding: utf-8

from gevent import monkey
monkey.patch_all()
from gevent.pool import Pool
import gevent
import requests
import os
import time

def urljoin(a, b):
    # add a slash if needed
    if a[-1] != '/':
        a += '/'
    # remove a slash if needed
    if b[0] == '/':
        b = b[1:]
    return a + b

class Downloader:
    def __init__(self, pool_size, retry=3):
        self.pool = Pool(pool_size)
        self.session = self._get_http_session(pool_size, pool_size, retry)
        self.retry = retry
        self.dir = ''
        self.succed = {}
        self.failed = []
        self.ts_total = 0
        self._result_file_name = None

    def _get_http_session(self, pool_connections, pool_maxsize, max_retries):
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(pool_connections=pool_connections, pool_maxsize=pool_maxsize, max_retries=max_retries)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            return session

    def run(self, m3u8_url, dir=''):
        self.dir = dir
        if self.dir and not os.path.isdir(self.dir):
            os.makedirs(self.dir)
        r = self.session.get(m3u8_url, timeout=10)
        if r.ok:
            body = r.content
            if body:
                ts_list = [urljoin(m3u8_url, n.strip()) for n in body.decode().split('\n') if n and not n.startswith("#")]
                if len(ts_list) == 1:
                    file_name = ts_list[0].split('/')[-1].split('?')[0]
                    chunk_list_url = "{0}/{1}".format(m3u8_url[:m3u8_url.rfind('/')], file_name)
                    print("Getting chunklist at: {0}".format(chunk_list_url))
                    r = self.session.get(chunk_list_url, timeout=20)
                    if r.ok:
                        body = r.content
                        ts_list = [urljoin(m3u8_url, n.strip()) for n in body.decode().split('\n') if n and not n.startswith("#")]
                    # re-retrieve to get all ts file list

                ts_list = zip(ts_list, [n for n in range(len(ts_list))])
                ts_list = list(ts_list)

                if ts_list:
                    self.ts_total = len(ts_list)
                    print('ts total: {0}'.format(self.ts_total))
                    g1 = gevent.spawn(self._join_file)
                    self._download(ts_list)
                    g1.join()
        else:
            print(r.status_code)
        infile_name = os.path.join(self.dir, self._result_file_name.split('.')[0]+'_all.'+self.result_file_name.split('.')[-1])
        outfile_name = infile_name.split('.')[0] + '.mp4'
        print('Converting "{0}" to "{1}"'.format(infile_name, outfile_name))
        from ffmpy import FFmpeg
        ff = FFmpeg(
            inputs={infile_name: None},
            outputs={outfile_name: ['-c','copy']}
        )
        ff.run()
        # delete source file after done
        os.remove(os.path.join(self.dir, infile_name))
        self._result_file_name = outfile_name

    def _download(self, ts_list):
        self.pool.map(self._worker, ts_list)
        if self.failed:
            ts_list = self.failed
            self.failed = []
            self._download(ts_list)

    def _worker(self, ts_tuple):
        url = ts_tuple[0]
        index = ts_tuple[1]
        retry = self.retry
        while retry:
            try:
                r = self.session.get(url, timeout=20)
                if r.ok:
                    file_name = url.split('/')[-1].split('?')[0]
                    print('Downloading: {0}'.format(file_name))
                    with open(os.path.join(self.dir, file_name), 'wb') as f:
                        f.write(r.content)
                    self.succed[index] = file_name
                    return
            except:
                retry -= 1
        print('[FAIL]%s' % url)
        self.failed.append((url, index))

    def _join_file(self):
        index = 0
        outfile = ''
        while index < self.ts_total:
            file_name = self.succed.get(index, '')
            if file_name:
                if self._result_file_name is None:
                    self._result_file_name = file_name
                infile = open(os.path.join(self.dir, file_name), 'rb')
                if not outfile:
                    outfile = open(os.path.join(self.dir, file_name.split('.')[0]+'_all.'+file_name.split('.')[-1]), 'wb')
                outfile.write(infile.read())
                infile.close()
                os.remove(os.path.join(self.dir, file_name))
                index += 1
            else:
                time.sleep(1)
        if outfile:
            outfile.close()

    @property
    def result_file_name(self):
        return self._result_file_name

if __name__ == '__main__':
    downloader = Downloader(50)
    # downloader.run('http://m3u8.test.com/test.m3u8', '/home/soraxas/Videos/')
    #downloader.run('http://delivery.streaming.sydney.edu.au:1935/echo/_definst_/1731/3/ba3eddeb-f00e-405a-98bb-1ed19157ffa8/mp4:audio-vga-streamable.m4v/playlist.m3u8', '/home/soraxas/Videos/')
    downloader.run('http://delivery.streaming.sydney.edu.au:1935/echo/_definst_/1741/3/1a700a60-d42f-4e24-bd5d-d23d2d8dd134/mp4:audio-vga-streamable.m4v/playlist.m3u8', '/home/soraxas/Videos/')
    print('DONE')
