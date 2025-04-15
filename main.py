#!/usr/bin/env python
# -*- coding: utf-8 -*-

# =============================================================================
#  Version: 0.01 (March 13, 2025)
#  Author: Evin Tunador (evintunador@gmail.com)
#
#  Contributors (pre-fork):
#   Giuseppe Attardi, University of Pisa (author pre-fork)
#   Antonio Fuschetto 
#   Leonardo Souza
#   Juan Manuel Caicedo 
#   Humberto Pereira 
#   Siegfried-A. Gevatter 
#   Pedro Assis 
#   Wim Muskee 
#   Radics Geza 
#   Nick Ulven 
#
# =============================================================================
#  Copyright (c) 2025. Evin Tunador (evintunador@gmail.com).
# =============================================================================
#  This file is part of Tanl.
#
#  Tanl is free software; you can redistribute it and/or modify it
#  under the terms of the GNU Affero General Public License, version 3,
#  as published by the Free Software Foundation.
#
#  Tanl is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
# =============================================================================

"""Wikipedia Extractor:
Extracts and cleans text from a Wikipedia database dump and stores output as 
individual markdown files in a given directory. Each file will be named after 
the page title and contain a single Wikipedia article.

The program performs template expansion by preprocessing the whole dump and
collecting template definitions.
"""

import argparse
import bz2
import logging
import os.path
import re
import sys
from io import StringIO
from multiprocessing import Queue, get_context, cpu_count
from timeit import default_timer

from extract import Extractor, ignoreTag, define_template, acceptedNamespaces

# ===========================================================================

##
# Defined in <siteinfo>
# We include as default Template, when loading external template file.
knownNamespaces = set(['Template'])

##
# The namespace used for template definitions
# It is the name associated with namespace key=10 in the siteinfo header.
templateNamespace = ''

##
# The namespace used for module definitions
# It is the name associated with namespace key=828 in the siteinfo header.
moduleNamespace = ''

# ----------------------------------------------------------------------
# Modules

# Only minimal support
# FIXME: import Lua modules.

modules = {
    'convert': {
        'convert': lambda x, u, *rest: x + ' ' + u,  # no conversion
    }
}

# ------------------------------------------------------------------------------
# Modified Output - one file per article


def get_safe_filename(title):
    """
    Convert article title to a safe filename
    """
    # Replace problematic characters with underscore
    safe_name = re.sub(r'[/\\?%*:|"<>\s]', '_', title)
    # Ensure filename is not too long
    if len(safe_name) > 200:
        safe_name = safe_name[:200]
    return safe_name + '.md'


class PageWriter:
    """
    Handles writing individual page files
    """
    def __init__(self, output_dir):
        self.output_dir = output_dir
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)
    
    def write_page(self, id, title, text):
        """
        Write a single page to a file named after the title
        """
        filename = get_safe_filename(title)
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
        return filepath


# ----------------------------------------------------------------------
# READER

tagRE = re.compile(r'(.*?)<(/?\w+)[^>]*>(?:([^<]*)(<.*?>)?)?')
#                    1     2               3      4


def load_templates(file, output_file=None):
    """
    Load templates from :param file:.
    :param output_file: file where to save templates and modules.
    :return: number of templates loaded.
    """
    global templateNamespace
    global moduleNamespace, modulePrefix
    modulePrefix = moduleNamespace + ':'
    articles = 0
    templates = 0
    page = []
    inText = False
    if output_file:
        output = open(output_file, 'w')
    for line in file:
        #line = line.decode('utf-8')
        if '<' not in line:  # faster than doing re.search()
            if inText:
                page.append(line)
            continue
        m = tagRE.search(line)
        if not m:
            continue
        tag = m.group(2)
        if tag == 'page':
            page = []
        elif tag == 'title':
            title = m.group(3)
            if not output_file and not templateNamespace:  # do not know it yet
                # we reconstruct it from the first title
                colon = title.find(':')
                if colon > 1:
                    templateNamespace = title[:colon]
                    Extractor.templatePrefix = title[:colon + 1]
            # FIXME: should reconstruct also moduleNamespace
        elif tag == 'text':
            inText = True
            line = line[m.start(3):m.end(3)]
            page.append(line)
            if m.lastindex == 4:  # open-close
                inText = False
        elif tag == '/text':
            if m.group(1):
                page.append(m.group(1))
            inText = False
        elif inText:
            page.append(line)
        elif tag == '/page':
            if title.startswith(Extractor.templatePrefix):
                define_template(title, page)
                templates += 1
            # save templates and modules to file
            if output_file and (title.startswith(Extractor.templatePrefix) or
                                title.startswith(modulePrefix)):
                output.write('<page>\n')
                output.write('   <title>%s</title>\n' % title)
                output.write('   <ns>10</ns>\n')
                output.write('   <text>')
                for line in page:
                    output.write(line)
                output.write('   </text>\n')
                output.write('</page>\n')
            page = []
            articles += 1
            if articles % 100000 == 0:
                logging.info("Preprocessed %d pages", articles)
    if output_file:
        output.close()
        logging.info("Saved %d templates to '%s'", templates, output_file)
    return templates


def decode_open(filename, mode='rt', encoding='utf-8'):
    """
    Open a file, decode and decompress, depending on extension `gz`, or 'bz2'.
    :param filename: the file to open.
    """
    ext = os.path.splitext(filename)[1]
    if ext == '.gz':
        import gzip
        return gzip.open(filename, mode, encoding=encoding)
    elif ext == '.bz2':
        return bz2.open(filename, mode=mode, encoding=encoding)
    else:
        return open(filename, mode, encoding=encoding)


def collect_pages(text):
    """
    :param text: the text of a wikipedia file dump.
    """
    # we collect individual lines, since str.join() is significantly faster
    # than concatenation
    page = []
    id = ''
    revid = ''
    last_id = ''
    inText = False
    redirect = False
    for line in text:
        if '<' not in line:     # faster than doing re.search()
            if inText:
                page.append(line)
            continue
        m = tagRE.search(line)
        if not m:
            continue
        tag = m.group(2)
        if tag == 'page':
            page = []
            redirect = False
        elif tag == 'id' and not id:
            id = m.group(3)
        elif tag == 'id' and id: # <revision> <id></id> </revision>
            revid = m.group(3)
        elif tag == 'title':
            title = m.group(3)
        elif tag == 'redirect':
            redirect = True
        elif tag == 'text':
            inText = True
            line = line[m.start(3):m.end(3)]
            page.append(line)
            if m.lastindex == 4:  # open-close
                inText = False
        elif tag == '/text':
            if m.group(1):
                page.append(m.group(1))
            inText = False
        elif inText:
            page.append(line)
        elif tag == '/page':
            colon = title.find(':')
            if ((colon < 0 or (title[:colon] in acceptedNamespaces)) and id != last_id and
                    not redirect and not title.startswith(templateNamespace)):
                yield (id, revid, title, page)
                last_id = id
            id = ''
            revid = ''
            page = []
            inText = False
            redirect = False


def process_dump(input_file, template_file, out_dir, process_count, 
                 html_safe=False, expand_templates=True):
    """
    :param input_file: name of the wikipedia dump file; '-' to read from stdin
    :param template_file: optional file with template definitions.
    :param out_dir: directory where to store extracted data
    :param process_count: number of extraction processes to spawn.
    :html_safe: whether to convert entities in text to HTML.
    :param expand_templates: whether to expand templates.
    """
    global knownNamespaces
    global templateNamespace
    global moduleNamespace, modulePrefix

    urlbase = ''                # This is obtained from <siteinfo>

    input = decode_open(input_file)

    # collect siteinfo
    for line in input:
        line = line #.decode('utf-8')
        m = tagRE.search(line)
        if not m:
            continue
        tag = m.group(2)
        if tag == 'base':
            # discover urlbase from the xml dump file
            # /mediawiki/siteinfo/base
            base = m.group(3)
            urlbase = base[:base.rfind("/")]
        elif tag == 'namespace':
            knownNamespaces.add(m.group(3))
            if re.search('key="10"', line):
                templateNamespace = m.group(3)
                Extractor.templatePrefix = templateNamespace + ':'
            elif re.search('key="828"', line):
                moduleNamespace = m.group(3)
                modulePrefix = moduleNamespace + ':'
        elif tag == '/siteinfo':
            break

    if expand_templates:
        # preprocess
        template_load_start = default_timer()
        if template_file and os.path.exists(template_file):
            logging.info("Preprocessing '%s' to collect template definitions: this may take some time.", template_file)
            file = decode_open(template_file)
            templates = load_templates(file)
            file.close()
        else:
            if input_file == '-':
                # can't scan then reset stdin; must error w/ suggestion to specify template_file
                raise ValueError("to use templates with stdin dump, must supply explicit template-file")
            logging.info("Preprocessing '%s' to collect template definitions: this may take some time.", input_file)
            templates = load_templates(input, template_file)
            input.close()
            input = decode_open(input_file)
        template_load_elapsed = default_timer() - template_load_start
        logging.info("Loaded %d templates in %.1fs", templates, template_load_elapsed)

    page_writer = PageWriter(out_dir)

    # process pages
    logging.info("Starting page extraction from %s.", input_file)
    extract_start = default_timer()

    # Parallel Map/Reduce:
    # - pages to be processed are dispatched to workers
    # - a reduce process collects the results and writes them to individual files.

    # fixes MacOS error: TypeError: cannot pickle '_io.TextIOWrapper' object
    Process = get_context("fork").Process

    maxsize = 10 * process_count
    # output queue
    output_queue = Queue(maxsize=maxsize)

    # Reduce job that writes individual files
    reduce = Process(target=reduce_process, args=(output_queue, page_writer))
    reduce.start()

    # initialize jobs queue
    jobs_queue = Queue(maxsize=maxsize)

    # start worker processes
    logging.info("Using %d extract processes.", process_count)
    workers = []
    for _ in range(max(1, process_count)):
        extractor = Process(target=extract_process,
                            args=(jobs_queue, output_queue, html_safe))
        extractor.daemon = True  # only live while parent process lives
        extractor.start()
        workers.append(extractor)

    # Mapper process

    # we collect individual lines, since str.join() is significantly faster
    # than concatenation

    ordinal = 0  # page count
    for id, revid, title, page in collect_pages(input):
        job = (id, revid, urlbase, title, page, ordinal)
        jobs_queue.put(job)  # goes to any available extract_process
        ordinal += 1

    input.close()

    # signal termination
    for _ in workers:
        jobs_queue.put(None)
    # wait for workers to terminate
    for w in workers:
        w.join()

    # signal end of work to reduce process
    output_queue.put(None)
    # wait for it to finish
    reduce.join()

    extract_duration = default_timer() - extract_start
    extract_rate = ordinal / extract_duration
    logging.info("Finished %d-process extraction of %d articles in %.1fs (%.1f art/s)",
                 process_count, ordinal, extract_duration, extract_rate)


# ----------------------------------------------------------------------
# Multiprocess support


def extract_process(jobs_queue, output_queue, html_safe):
    """Pull tuples of raw page content, do CPU/regex-heavy fixup, push finished text
    :param jobs_queue: where to get jobs.
    :param output_queue: where to queue extracted text for output.
    :html_safe: whether to convert entities in text to HTML.
    """
    while True:
        job = jobs_queue.get()  # job is (id, revid, urlbase, title, page)
        if job:
            out = StringIO()  # memory buffer
            # We need to modify the extract method to produce markdown output
            Extractor(*job[:-1]).extract(out, html_safe, markdown=True)  # (id, urlbase, title, page)
            text = out.getvalue()
            output_queue.put((job[-1], job[0], job[3], text))  # (ordinal, id, title, extracted_text)
            out.close()
        else:
            break


def reduce_process(output_queue, page_writer):
    """
    Pull finished article text, write to individual files
    :param output_queue: text to be output.
    :param page_writer: PageWriter object to handle file creation.
    """
    interval_start = default_timer()
    period = 1000
    pages_written = 0

    while True:
        # mapper puts None to signal finish
        item = output_queue.get()
        if not item:
            break
            
        ordinal, id, title, text = item
        page_writer.write_page(id, title, text)
        pages_written += 1
        
        # progress report
        if pages_written % period == 0:
            interval_rate = period / (default_timer() - interval_start)
            logging.info("Wrote %d articles (%.1f art/s)",
                         pages_written, interval_rate)
            interval_start = default_timer()


def main():
    global acceptedNamespaces

    parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]),
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=__doc__)
    parser.add_argument("input",
                        help="XML wiki dump file")
    parser.add_argument("-o", "--output", default="text",
                        help="output directory")
    parser.add_argument("-l", "--links", action="store_true", default=True,
                        help="preserve links in markdown format")
    parser.add_argument("-ns", "--namespaces", default="", metavar="ns1,ns2",
                        help="accepted namespaces")
    parser.add_argument("--templates",
                        help="use or create file containing templates")
    parser.add_argument("--no-templates", action="store_true",
                        help="Do not expand templates")
    default_process_count = cpu_count() - 1
    parser.add_argument("--processes", type=int, default=default_process_count,
                        help="Number of processes to use (default %(default)s)")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="suppress reporting progress info")
    parser.add_argument("--debug", action="store_true",
                        help="print debug info")

    args = parser.parse_args()

    # Always preserve links but in markdown format
    Extractor.keepLinks = args.links
    
    # We don't want HTML formatting
    Extractor.HtmlFormatting = False
    
    # We don't want JSON output
    Extractor.toJson = False

    if args.namespaces:
        acceptedNamespaces = set(args.namespaces.split(','))

    FORMAT = '%(levelname)s: %(message)s'
    logging.basicConfig(format=FORMAT)

    logger = logging.getLogger()
    if not args.quiet:
        logger.setLevel(logging.INFO)
    if args.debug:
        logger.setLevel(logging.DEBUG)

    input_file = args.input

    # Don't ignore links - we want to convert them to markdown
    if not Extractor.keepLinks:
        ignoreTag('a')

    output_path = args.output
    if not os.path.isdir(output_path):
        try:
            os.makedirs(output_path)
        except:
            logging.error('Could not create: %s', output_path)
            return

    # Process the dump, one file per article
    process_dump(input_file, args.templates, output_path, args.processes, 
                 html_safe=False, expand_templates=not args.no_templates)

if __name__ == '__main__':
    main()
