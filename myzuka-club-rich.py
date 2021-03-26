#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This work is free. You can redistribute it and/or modify it under the
# terms of the Do What The Fuck You Want To Public License, Version 2,
# as published by Sam Hocevar.  See the COPYING file for more details.

# Changelog:
# 5.10: corrections, cosmetic
# 5.9: corrections, cosmetic
# 5.8: better rich interface
# 5.7: add support for "rich" output and changed the multithreading module
# 5.6: better support for Tor socks proxy, and support for "requests" module instead of 
#      "urllib.request", because cloudflare seems to block more "urllib.request" than "requests", 
#      even with the same headers...

live = 1
site = "http://myzuka.club"
userequests = 1
version = 5.10
useragent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:86.0) Gecko/20100101 Firefox/86.0"
min_page_size = 8192
covers_name = "cover.jpg"
warning_color = "bold yellow"
error_color = "bold red"
ok_color = "bold green"
debug_color = "bold blue"
min_retry_delay = 3
max_retry_delay = 10

import re
import sys
import os
import time
import random
import socks
import socket
import html
import argparse
import traceback
import signal
from bs4 import BeautifulSoup
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import threading

import faulthandler  # kill this script with SIGABRT in case of deadlock to see the stacktrace.
faulthandler.enable()

## Rich definitions ##
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.console import Console
# from rich.text import Text
# from rich.align import Align

# from rich import inspect
# Rich can be installed as the default traceback handler so that all 
# uncaught exceptions will be rendered with highlighting.
# from rich.traceback import install
# install()

from rich.progress import (
    BarColumn,
    DownloadColumn,
    TextColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
    Progress,
    TaskID,
)


class Header:
    """Display header with clock."""

    def __rich__(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="center", ratio=1)
        grid.add_column(justify="right")
        grid.add_row(
            "[b]Music[/b] downloader, use Ctrl-c to exit (in Windows, "
            + "you sometimes have to kill/close the console)",
            datetime.now().ctime().replace(":", "[blink]:[/]"),
        )
        return Panel(grid, style="white on black")


def make_layout() -> Layout:
    """Define the layout."""
    layout = Layout(name="root")

    layout.split(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
    )
    layout["main"].split(
        Layout(name="left"),
        Layout(name="center", ratio=2),
        Layout(name="right", ratio=1),
        direction="horizontal",
    )
    return layout


layout = make_layout()
console = Console()
infos_table = Table(show_header=False)
errors_table = Table(show_header=False)
errors_console = Console()
#errors_text = Text()
progress_table = Table.grid(expand=True)
dl_progress = Progress()


def reset_errors():
    global errors_table
    errors_table = Table(show_header=False)
    #layout["right"].update(Panel(errors_table))


def reset_progress():
    global dl_progress
    dl_progress = Progress(
        TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        DownloadColumn(),
        "•",
        TransferSpeedColumn(),
        "•",
        TimeRemainingColumn(),
    )
    global progress_table
    progress_table = Table.grid(expand=True)
    progress_table.add_row(
        Panel(
            dl_progress,
            title="Tracks Progress",
            border_style="green",
            padding=(2, 2),
        ),
    )
    layout["center"].update(progress_table)


## END OF Rich definitions ##


def script_help(version, script_name):
    description = "Python script to download albums from %s, version %.2f." % (site, version)
    help_string = (description + """

------------------------------------------------------------------------------------------------------------------
################## To download an album, give it an url with '/Album/' in it #####################################
------------------------------------------------------------------------------------------------------------------
user@computer:/tmp$ %s [-p /path] %s/Album/630746/The-6-Cello-Suites-Cd1-1994
** We will try to use 3 simultaneous downloads, progress will be shown **
** after each completed file but not necessarily in album's order. **

Artist: Johann Sebastian Bach
Album: The 6 Cello Suites (CD1)
Year: 1994
cover.jpg                                                 00.01 of 00.01 MB [100%%]
05_johann_sebastian_bach_maurice_gendron_bwv1007_menuets_myzuka.mp3        07.04 of 07.04 MB [100%%]
01_johann_sebastian_bach_maurice_gendron_bwv1007_prelude_myzuka.mp3        05.57 of 05.57 MB [100%%]
03_johann_sebastian_bach_maurice_gendron_bwv1007_courante_myzuka.mp3        05.92 of 05.92 MB [100%%]
06_johann_sebastian_bach_maurice_gendron_bwv1007_gigue_myzuka.mp3        04.68 of 04.68 MB [100%%]
04_johann_sebastian_bach_maurice_gendron_bwv1007_sarabande_myzuka.mp3        07.06 of 07.06 MB [100%%]
[...]

It will create an "Artist - Album" directory in the path given as argument (or else in current
 directory if not given), and download all songs and covers available on that page.


------------------------------------------------------------------------------------------------------------------
################## To download all albums from an artist, give it an url with '/Artist/' in it ###################
------------------------------------------------------------------------------------------------------------------

user@computer:/tmp$ %s [-p /path] %s/Artist/7110/Johann-Sebastian-Bach/Albums
** We will try to use 3 simultaneous downloads, progress will be shown **
** after each completed file but not necessarily in album's order. **
** Warning: we are going to download all albums from this artist! **

Artist: Johann Sebastian Bach
Album: The 6 Cello Suites (CD1)
Year: 1994
cover.jpg                                                 00.01 of 00.01 MB [100%%]
05_johann_sebastian_bach_maurice_gendron_bwv1007_menuets_myzuka.mp3        07.04 of 07.04 MB [100%%]
01_johann_sebastian_bach_maurice_gendron_bwv1007_prelude_myzuka.mp3        05.57 of 05.57 MB [100%%]
03_johann_sebastian_bach_maurice_gendron_bwv1007_courante_myzuka.mp3        05.92 of 05.92 MB [100%%]
[...]

Artist: Johann Sebastian Bach
Album: Prelude and Fugue in E Minor, BWV 548
Year: 1964
cover.jpg                                                 00.01 of 00.01 MB [100%%]
01_johann_sebastian_bach_praeludium_myzuka.mp3            09.51 of 09.51 MB [100%%]
02_johann_sebastian_bach_fuga_myzuka.mp3                  10.80 of 10.80 MB [100%%]
** ALBUM DOWNLOAD FINISHED **

[...]


It will iterate on all albums of this artist.


------------------------------------------------------------------------------------------------------------------
################# Command line help ##############################################################################
------------------------------------------------------------------------------------------------------------------

For more info, see https://github.com/damsgithub/myzuka-club.py


"""
        % (script_name, site, script_name, site)
    )
    return help_string


def pause_between_retries():
    time.sleep(random.randint(min_retry_delay, max_retry_delay))


def to_MB(a_bytes):
    return a_bytes / 1024.0 / 1024.0


def log_to_file(function, content):
    timestr = time.strftime("%Y%m%d-%H%M%S")
    mylogname = "myzukalog-" + function + "-" + timestr + ".log"
    logcontent = open(mylogname, "w", encoding="utf-8")
    logcontent.write(content)
    logcontent.close()


def color_message(msg, color):
    if live:
        # Text test
        # layout["right"].update(
        #     Align.center(errors_text.append(datetime.now().ctime() + " " + msg + "\n", style=color),
        #     vertical="bottom")
        # )
        #layout["right"].update(errors_text)
        
        ## Console test
        # with errors_console.pager():
        #     errors_console.print(msg)
        # layout["right"].update(errors_console)

        # Table test
        errors_table.add_row("[" + color + "]" + msg)
        layout["right"].update(Panel(errors_table))
    else:
        console.print(msg, style=color)


def dl_status(file_name, dlded_size, real_size):
    status = r"%-50s        %05.2f of %05.2f MB [%3d%%]" % (
        file_name,
        to_MB(dlded_size),
        to_MB(real_size),
        dlded_size * 100.0 / real_size,
    )
    return status


def download_cover(page_content, url, debug, socks_proxy, socks_port, timeout, task_id, event):
    # download album's cover(s)
    cover_url_re = re.compile('<img alt=".+?" itemprop="image" src="(.+?)"/>')
    cover_url_match = cover_url_re.search(page_content)

    cover_url = cover_url_match.group(1)

    if debug:
        color_message("cover: %s" % cover_url, debug_color)

    if not cover_url:
        color_message("** No cover found for this album **", warning_color)
    else:
        download_file(cover_url, covers_name, debug, socks_proxy, socks_port, timeout, task_id, event)


def get_base_url(url, debug):
    # get website base address to preprend it to images, songs and albums relative urls'
    base_url = url.split("//", 1)
    base_url = base_url[0] + "//" + base_url[1].split("/", 1)[0]
    return base_url


def open_url(url, debug, socks_proxy, socks_port, timeout, event, data, range_header):
    if socks_proxy and socks_port:
        socks.set_default_proxy(
            socks.SOCKS5, socks_proxy, socks_port, True
        )  # 4th parameter is to do dns resolution through the socks proxy
        socket.socket = socks.socksocket

    while True:
        if event.is_set():
            raise KeyboardInterrupt
        # else: color_message("open_url: NOT SET", error_color)

        if not userequests:
            import urllib.request
            if debug:
                color_message("open_url: %s" % url, debug_color)

            myheaders = {"User-Agent": useragent, "Referer": site}
            req = urllib.request.Request(url, data, headers=myheaders)
            if range_header:
                req.add_header("Range", range_header)

            try:
                u = urllib.request.urlopen(req, timeout=timeout)
                if debug > 1:
                    color_message("HTTP reponse code: %s" % u, debug_color)
            except urllib.error.HTTPError as e:
                if debug:
                    color_message("** urllib.error.HTTPError (%s), reconnecting **" 
                        % e.reason, warning_color)
                pause_between_retries()
                continue
            except urllib.error.URLError as e:
                if re.search("timed out", str(e.reason)):
                    # on linux "timed out" is a socket.timeout exception,
                    # on Windows it is an URLError exception....
                    if debug:
                        color_message("** Connection timeout (%s), reconnecting **" 
                            % e.reason, warning_color)
                    pause_between_retries()
                    continue
                else:
                    color_message("** urllib.error.URLError, aborting **" % e.reason, error_color)
                    u = None
            except (socket.timeout, socket.error, ConnectionError) as e:
                if debug:
                    color_message("** Connection problem 2 (%s), reconnecting **" 
                        % str(e), warning_color)
                pause_between_retries()
                continue
            except Exception as e:
                color_message("** Exception: aborting (%s) with error: %s **" 
                    % (url, str(e)), error_color)
                u = None

        else:
            import cfscrape
            import requests
            scraper = cfscrape.create_scraper()
            # the "h" after socks5 is to make the dns resolution through the socks proxy
            if socks_proxy and socks_port:
                proxies = {
                    "http": "socks5h://" + socks_proxy + ":" + str(socks_port),
                    "https": "socks5h://" + socks_proxy + ":" + str(socks_port),
                }
            else:
                proxies = {}

            try:
                if range_header:
                    myheaders = {"User-Agent": useragent, "Referer": site, "Range": range_header}
                    # u = requests.get(url, proxies=proxies, headers=myheaders, timeout=timeout, stream=True)
                    u = scraper.get(url, proxies=proxies, headers=myheaders, timeout=timeout, stream=True)
                else:
                    myheaders = {"User-Agent": useragent, "Referer": site}
                    # u = requests.get(url, proxies=proxies, headers=myheaders, timeout=timeout)
                    u = scraper.get(url, proxies=proxies, headers=myheaders, timeout=timeout, stream=True)

                u.raise_for_status()
                if debug > 1:
                    color_message("HTTP reponse code: %s" % u, debug_color)
            except requests.exceptions.HTTPError as e:
                color_message("** requests.exceptions.HTTPError (%s), reconnecting **" 
                    % str(e), warning_color)
                pause_between_retries()
                continue
            except requests.exceptions.ConnectionError as e:
                color_message("**  requests.exceptions.ConnectionError (%s), reconnecting **" 
                    % str(e), warning_color)
                pause_between_retries()
                continue
            except requests.exceptions.Timeout as e:
                color_message("** Connection timeout (%s), reconnecting **" 
                    % str(e), warning_color)
                pause_between_retries()
                continue
            except requests.exceptions.RequestException as e:
                color_message("** Exception: aborting (%s) with error: %s **" 
                    % (url, str(e)), error_color)
                u = None
            except (socket.timeout, socket.error, ConnectionError) as e:
                color_message("** Connection problem 2 (%s), reconnecting **" 
                    % str(e), warning_color)
                pause_between_retries()
                continue
            except Exception as e:
                color_message("** Exception: aborting (%s) with error: %s **" 
                    % (url, str(e)), error_color)
                u = None

        return u


def get_page_soup(url, data, debug, socks_proxy, socks_port, timeout, event):
    page = open_url(url, debug, socks_proxy, socks_port, timeout, event, data=data, range_header=None)
    if not page:
        return None
    if not userequests:
        page_soup = BeautifulSoup(page, "html.parser", from_encoding=page.info().get_param("charset"))
    else:
        page_soup = BeautifulSoup(page.content, "html.parser", from_encoding=page.encoding)
    page.close()
    return page_soup


def prepare_album_dir(page_content, base_path, debug):
    # get album infos from html page content
    artist = ""
    title = ""
    year = ""

    if debug > 1:
        log_to_file("prepare_album_dir", page_content)

    color_message("", ok_color)

    # find artist name
    artist_info_re = re.compile(
        "<td>Исполнитель:</td>\r?\n?"
        "(?:\s)*<td>\r?\n?"
        "(?:\r?\n?)*"
        "(?:\s)*<a (?:.+?)>\r?\n?"
        '(?:\s)*<meta (?:.+?)itemprop="url"(?:.*?)(?:\s)*/>\r?\n?'
        '(?:\s)*<meta (?:.+?)itemprop="name"(?:.*?)(?:\s)*/>\r?\n?'
        "(?:\r?\n?)*"
        "(?:\s)*(.+?)\r?\n?"
        "(?:\r?\n?)*"
        "(?:\s)*</a>"
    )
    artist_info = artist_info_re.search(page_content)

    if not artist_info:
        artist = input("Unable to get ARTIST NAME. Please enter here: ")
    else:
        artist = artist_info.group(1)

    # find album name
    title_info_re = re.compile(
        '<span itemprop="title">(?:.+?)</span>\r?\n?'
        "(?:\r?\n?)*"
        "(?:\s)*</a>/\r?\n?"
        "(?:\r?\n?)*"
        '(?:\s)*<span (?:.*?)itemtype="http://data-vocabulary.org/Breadcrumb"(?:.*?)>(.+?)</span>'
    )
    title_info = title_info_re.search(page_content)

    if not title_info:
        title = input("Unable to get ALBUM NAME. Please enter here: ")
    else:
        title = title_info.group(1)

    # Get the year if it is available
    year_info_re = re.compile('<time datetime="(\d+).*?" itemprop="datePublished"></time>\r?\n?')

    year_info = year_info_re.search(page_content)

    if year_info and year_info.group(1):
        year = year_info.group(1)
    else:
        year = input("Unable to get ALBUM YEAR. Please enter here (may leave blank): ")

    infos_table.add_row(artist + " - " + title + " - " + year)
    layout["left"].update(Panel(infos_table))

    # prepare album's directory
    if year:
        album_dir = artist + " - " + title + " (" + year + ")"
    else:
        album_dir = artist + " - " + title

    album_dir = os.path.normpath(base_path + os.sep + sanitize_path(album_dir))
    if debug:
        color_message("Album's dir: %s" % (album_dir), debug_color)

    if not os.path.exists(album_dir):
        os.mkdir(album_dir)

    return album_dir


def sanitize_path(path):
    chars_to_remove = str.maketrans('/\\?*|":><', "         ")
    return path.translate(chars_to_remove)


def get_filename_from_cd(cd):
    # Get filename from content-disposition
    if not cd:
        return None
    fname = re.findall("filename=(.+)", cd)
    if len(fname) == 0:
        return None
    return fname[0]


def download_file(url, file_name, debug, socks_proxy, socks_port, timeout, task_id: TaskID, event):
    process_id = os.getpid()
    try:
        real_size = -1
        partial_dl = 0
        dlded_size = 0
        block_sz = 8192

        u = open_url(url, debug, socks_proxy, socks_port, timeout, event, data=None, range_header=None)
        if not u:
            return -1

        if not file_name:
            if not userequests:
                file_name = u.info().get_filename()
            else:
                file_name = get_filename_from_cd(u.headers.get("content-disposition"))
        
        file_name = file_name.replace("_myzuka", "")
        
        if debug > 1:
            color_message("filename: %s" % file_name, debug_color)
                
        if os.path.exists(file_name):
            dlded_size = os.path.getsize(file_name)

        if dlded_size <= min_page_size and file_name != covers_name:
            # we may have got an "Exceed the download limit" (Превышение лимита скачивания) 
            # page instead of the song, better restart at beginning.
            dlded_size = 0

        i = 0
        while i < 5:
            try:
                if not userequests:
                    real_size = int(u.info()["content-length"])
                else:
                    real_size = int(u.headers["Content-length"])
                if debug > 1:
                    color_message("length: %s" % real_size, debug_color)
                if real_size <= min_page_size and (file_name != covers_name):
                    # we may have got an "Exceed the download limit" (Превышение лимита скачивания)
                    # page, retry
                    color_message(
                        "** Served file (%s) too small (<= %s), retrying (verify this file after download) **"
                        % (file_name, min_page_size),
                        warning_color
                    )
                    i += 1
                    continue
                break
            except Exception as e:
                if i == 4:
                    if debug:
                        color_message(
                            "** Unable to get the real size of %s from the server because: %s. **"
                            % (file_name, str(e)),
                            warning_color,
                        )
                    break  # real_size == -1
                else:
                    i += 1
                    if debug:
                        color_message(
                            "** %s problem while getting content-length: %s, retrying **" 
                                % (process_id, str(e)),
                            warning_color,
                        )
                    continue

        # find where to start the file download (continue or start at beginning)
        if 0 < dlded_size < real_size:
            # file incomplete, we need to resume download at correct range
            u.close()

            range_header = "bytes=%s-%s" % (dlded_size, real_size)
            data = None
            u = open_url(url, debug, socks_proxy, socks_port, timeout, event, data, range_header)
            if not u:
                return -1

            # test if the server supports the Range header
            range_support = ""
            if not userequests:
                range_support = u.getcode()
            else:
                range_support = u.status_code

            if range_support == 206:
                partial_dl = 1
            else:
                if debug:
                    color_message(
                        "** Range/partial download is not supported by server, "
                        + "restarting download at beginning **",
                        warning_color,
                    )
                dlded_size = 0
        elif dlded_size == real_size:
            # file already completed, skipped
            color_message("%s (already complete)" % file_name.split("_")[0], ok_color)
            u.close()
            dl_progress.start_task(task_id)
            dl_progress.update(task_id, total=int(real_size), advance=dlded_size)
            return
        elif dlded_size > real_size:
            # we got a problem, restart download from start
            color_message(f"** {file_name} is already bigger ({dlded_size}) than the server side "
                            f"file ({real_size}). Either server side file size could not be determined "
                            f"or an other problem occured, check file manually **",
                warning_color
            )
            u.close()
            return

        # show progress
        dl_progress.start_task(task_id)
        dl_progress.update(task_id, total=int(real_size), advance=dlded_size)

        # append or truncate
        if partial_dl:
            f = open(file_name, "ab+")
        else:
            f = open(file_name, "wb+")

        if real_size < block_sz:
            block_sz = 512

        # get the file
        if not userequests:
            while True:
                buffer = u.read(block_sz)
                if not buffer:
                    break
                else:
                    dlded_size += len(buffer)
                    f.write(buffer)
                    dl_progress.update(task_id, advance=len(buffer))
                    if event.is_set():
                        u.close()
                        f.close()
                        raise KeyboardInterrupt
                    # else: color_message("download_file: NOT SET", error_color)
        else:
            for buffer in u.iter_content(chunk_size=block_sz):
                if not buffer:
                    break
                else:
                    dlded_size += len(list(buffer))
                    f.write(buffer)
                    dl_progress.update(task_id, advance=len(list(buffer)))
                    if event.is_set():
                        u.close()
                        f.close()
                        raise KeyboardInterrupt
                    # else: color_message("download_file: NOT SET", error_color)

        if real_size == -1:
            real_size = dlded_size
            if debug:
                color_message(
                    "%s (file downloaded, but could not verify if it is complete)"
                    % dl_status(file_name, dlded_size, real_size),
                    warning_color,
                )
            # dl_progress.stop_task(task_id)
        elif real_size == dlded_size: # file downloaded and complete
            if not live:
                color_message(
                    "%s" % dl_status(file_name, dlded_size, real_size), ok_color
                )
            # dl_progress.stop_task(task_id)
        elif dlded_size < real_size:
            if debug:
                color_message(
                    "%s (file download incomplete, retrying)" 
                    % dl_status(file_name, dlded_size, real_size),
                    warning_color,
                )
            u.close()
            f.close()
            return -1

        u.close()
        f.close()
    except KeyboardInterrupt as e:
        if debug:
            color_message("** %s : download_file: keyboard interrupt detected **" 
                % process_id, error_color)
        raise e
    except Exception as e:
        if debug:
            color_message(
                '** Exception caught in download_file(%s,%s) with error: "%s". We will continue anyway. **'
                % (url, file_name, str(e)),
                warning_color,
            )
            traceback.print_exc()
        return -1


def download_song(num_and_url, debug, socks_proxy, socks_port, timeout, task_id: TaskID, event) -> None:
    process_id = os.getpid()

    m = re.match(r"^(\d+)-(.+)", num_and_url)
    tracknum = m.group(1)
    url = m.group(2)

    while True:  # continue until we have the song
        try:
            if event.is_set():
                raise KeyboardInterrupt

            if debug:
                color_message("%s: downloading song from %s" % (process_id, url), debug_color)

            file_name = ""
            file_url = ""

            page_soup = get_page_soup(url, None, debug, socks_proxy, socks_port, timeout, event)
            if not page_soup:
                if debug:
                    color_message("** %s: Unable to get song's page soup, retrying **" 
                        % process_id, debug_color)
                pause_between_retries()
                continue

            # get the file url
            for link in page_soup.find_all("a", href=True, class_="no-ajaxy", itemprop="audio", limit=1):
                file_url = link.get("href")
                break

            # prepend base url if necessary
            if re.match(r"^/", file_url):
                file_url = get_base_url(url, debug) + file_url

            # download song
            ret = download_file(file_url, file_name, debug, socks_proxy, socks_port, timeout, task_id, event)
            if ret == -1:
                if debug:
                    color_message(
                        "** %s: Problem detected while downloading %s, retrying **" 
                        % (process_id, file_name),
                        warning_color,
                    )
                pause_between_retries()
                continue
            else:
                if not live:
                    color_message("** downloaded: %s **" % (file_name), ok_color)
                break
        except KeyboardInterrupt:
            if debug:
                color_message(
                    "** %s: download_song: keyboard interrupt detected, finishing process **" 
                    % process_id,
                    error_color
                )
            raise
        except Exception as e:
            if debug:
                color_message(
                    '** %s: Exception caught in download_song(%s,%s) with error: "%s", retrying **'
                    % (process_id, url, file_name, str(e)),
                    warning_color,
                )
            pause_between_retries()
            pass


def download_album(url, base_path, debug, socks_proxy, socks_port, timeout, nb_conn, event):
    reset_errors()
    reset_progress()

    page_soup = get_page_soup(url, None, debug, socks_proxy, socks_port, timeout, event)
    if not page_soup:
        color_message("** Unable to get album's page soup **", error_color)
        return
    page_content = str(page_soup)

    # Beautifulsoup converts "&" to "&amp;" so that it be valid html. 
    # We need to convert them back with html.unescape.
    page_content = html.unescape(page_content)

    album_dir = prepare_album_dir(page_content, base_path, debug)

    os.chdir(album_dir)

    download_cover(
        page_content,
        url,
        debug,
        socks_proxy,
        socks_port,
        timeout,
        dl_progress.add_task("download", filename=covers_name, start=False),
        event,
    )

    # create list of album's songs
    songs_links = []
    tracknum = 0
    absent_track_flag = 0

    for link in page_soup.find_all("a", href=re.compile("^/Song/"), title=re.compile("^Скачать")):
        # search track number

        tracknum_infos_re = re.compile(
            '<div class="position">\r?\n?'
            "(?:\r?\n?)*"
            "(?:\s)*(\d+)\r?\n?"
            "(?:\r?\n?)*"
            "(?:\s)*</div>\r?\n?"
            '(?:\s)*<div class="options">\r?\n?'
            '(?:\s)*<div class="top">\r?\n?'
            '(?:\s)*<span (?:.+?)title="Сохранить в плейлист"(?:.*?)></span>\r?\n?'
            '(?:\s)*<span (?:.+?)title="Добавить в плеер"(?:.*?)>(?:.*?)</span>\r?\n?'
            '(?:\s)*<a href="' + link["href"],
            re.I,
        )

        tracknum_infos = tracknum_infos_re.search(page_content)
        if tracknum_infos:
            tracknum = tracknum_infos.group(1)
            tracknum = str(tracknum).zfill(2)
        else:
            if debug:
                color_message("** Unable to get track number for %s **" % link["href"], warning_color)
            tracknum = 0

        # prepend base url if necessary
        if re.match(r"^/", link["href"]):
            link["href"] = get_base_url(url, debug) + link["href"]

        # add song url and number in array
        songs_links.append(str(tracknum) + "-" + link["href"])

    if debug > 1:
        log_to_file("download_album", page_content)

    # search for absent/deleted tracks from the website.
    deleted_track_re = re.compile(
        r'<div class="position">\r?\n?'
        "(?:\r?\n?)?"
        "(?:\s)*(\d+)\r?\n?"
        "(?:\r\n?)?"
        "(?:\s)*</div>\r?\n?"
        '(?:\s)*<div class="options">\r?\n?'
        '(?:\s)*<div class="top">\r?\n?'
        '(?:\s)*<span class=".*?glyphicon-ban-circle.*?"></span>\r?\n?'
        "(?:\s)*</div>\r?\n?"
        '(?:\s)*<div class="data">(?:.+?)</div>\r?\n?'
        "(?:\s)*</div>\r?\n?"
        '(?:\s)*<div class="details">\r?\n?'
        '(?:\s)*<div class="time">(?:.+?)</div>\r?\n?'
        "(?:\s)*<a (?:.+?)\r?\n?"
        "(?:\s)*<meta (?:.+?)\r?\n?"
        "(?:\s)*<meta (?:.+?)\r?\n?"
        "(?:\s)*</span>\r?\n?"
        "(?:\s)*<p>\r?\n?"
        "(?:\s)*<span>(.+?)</span> <span class=(?:.+?)>\[Удален по требованию правообладателя\]</span>"
    )

    for deleted_track in re.findall(deleted_track_re, page_content):
        tracknum = deleted_track[0]
        trackname = deleted_track[1]
        if debug:
            color_message(
                "** The track number %s (%s) is absent from website **" 
                % (tracknum, trackname), warning_color
            )
        absent_track_flag = 1

    if not songs_links:
        color_message("** Unable to detect any song links, skipping this album/url **", error_color)
        absent_track_flag = 1
    else:
        # we launch the threads to do the downloads
        try:
            with ThreadPoolExecutor(max_workers=nb_conn) as pool:
                for num_and_url in songs_links:
                    task_id = dl_progress.add_task("download", filename=num_and_url.split("/")[-1], start=False)
                    pool.submit(download_song, num_and_url, debug, socks_proxy, socks_port, timeout, task_id, event)
                    if event.is_set():
                        # color_message("** download_album: IS SET", error_color)
                        raise KeyboardInterrupt
            pool.shutdown()
        except KeyboardInterrupt as e:
            if debug:
                color_message("** download_album: Program interrupted by user, exiting! **", 
                    error_color)
            # pool.terminate()
            # pool.join()
            # pool.shutdown()
            # sys.exit(1)
            # os._exit(1)
            exit(1)
        except Exception as e:
            color_message(
                '** Exception caught in download_album(%s) with error: "%s", retrying **'
                % (url, str(e)),
                warning_color,
            )

    os.chdir("..")

    if not absent_track_flag and not event.is_set():
        infos_table.add_row("[" + ok_color + "]" + "** %s FINISHED **" % album_dir)
    else:
        infos_table.add_row("[" + error_color + "]" 
            + "** %s INCOMPLETE (tracks missing on website or user exit) **" % album_dir)
    layout["left"].update(Panel(infos_table))


def download_artist(url, base_path, debug, socks_proxy, socks_port, timeout, nb_conn, event):
    page_soup = get_page_soup(url, str.encode(""), debug, socks_proxy, socks_port, timeout, event)
    if not page_soup:
        if debug:
            color_message("** Unable to get artist's page soup **", error_color)
        return

    color_message("** Warning: we are going to download all albums from this artist! **", 
        warning_color)

    albums_links = []
    for link in page_soup.find_all("a", href=True):
        if re.search(r"/Album/.*", link["href"]):
            # albums' links may appear multiple times, we need to de-duplicate.
            if link["href"] not in albums_links:
                albums_links.append(link["href"])

    for album_link in albums_links:
        download_album(
            get_base_url(url, debug) + album_link, base_path, debug, socks_proxy, socks_port, timeout, nb_conn, event
        )
        if event.is_set():
            # color_message("** download_artist: IS SET", error_color)
            raise KeyboardInterrupt

    infos_table.add_row("[" + ok_color + "]" + "** ARTIST DOWNLOAD FINISHED **")
    layout["left"].update(Panel(infos_table))


def main():
    global version
    global live
    debug = 0
    socks_proxy = ""
    socks_port = ""
    timeout = 10
    nb_conn = 3
    script_name = os.path.basename(sys.argv[0])

    event = threading.Event()

    # "event" not being global, we need to define this function in this scope
    def signal_handler(signum, frame):
        event.set()
        color_message("SIGINT received, waiting to exit threads", error_color)

    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser(
        description=script_help(version, script_name), add_help=True, formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument("-d", "--debug", type=int, choices=range(0, 3), default=0, 
                        help="Debug verbosity: 0, 1, 2")
    parser.add_argument("-l", "--live", type=int, choices=range(0, 2), default=1, 
                        help="Use live display (rich): 0, 1")
    parser.add_argument("-s", "--socks", type=str, default=None, 
                        help='Socks proxy: "address:port" without "http://"')
    parser.add_argument("-t", "--timeout", type=int, default=10, 
                        help="Timeout for HTTP connections in seconds")
    parser.add_argument("-n", "--nb_conn", type=int, default=3, 
                        help="Number of simultaneous downloads (max 3 for tempfile.ru)")
    parser.add_argument("-p", "--path", type=str, default=".", 
                        help="Base directory in which album(s) will be downloaded. Defaults to current.")
    parser.add_argument("-v", "--version", action="version", version="%(prog)s, version: " + str(version))

    parser.add_argument("url", action="store", help="URL of album or artist page")

    args = parser.parse_args()

    debug = int(args.debug)
    if debug:
        color_message("Debug level: %s" % debug, debug_color)

    nb_conn = int(args.nb_conn)
    timeout = int(args.timeout)
    live = int(args.live)

    if args.socks:
        (socks_proxy, socks_port) = args.socks.split(":")
        if debug:
            color_message("proxy socks: %s %s" % (socks_proxy, socks_port), debug_color)
        if not socks_port.isdigit():
            color_message("** Error in your socks proxy definition, exiting. **", error_color)
            sys.exit(1)
        socks_port = int(socks_port)

    try:
        layout["header"].update(Header())
        reset_errors()
        reset_progress()

        if live:
            with Live(layout, refresh_per_second=4, vertical_overflow="visible"):
                # modification and access of "global" variables do not work correctly under Windows 
                # with multiprocessing, so I have to pass all these parameters to these functions...
                if re.search(r"/Artist/.*", args.url, re.IGNORECASE):
                    download_artist(args.url, args.path, debug, socks_proxy, socks_port, timeout, nb_conn, event)
                elif re.search(r"/Album/.*", args.url, re.IGNORECASE):
                    download_album(args.url, args.path, debug, socks_proxy, socks_port, timeout, nb_conn, event)
                else:
                    color_message(
                        "** Error: unable to recognize url, it should contain '/Artist/' or '/Album/'! **",
                        error_color
                    )
        else:
            if re.search(r"/Artist/.*", args.url, re.IGNORECASE):
                download_artist(args.url, args.path, debug, socks_proxy, socks_port, timeout, nb_conn, event)
            elif re.search(r"/Album/.*", args.url, re.IGNORECASE):
                download_album(args.url, args.path, debug, socks_proxy, socks_port, timeout, nb_conn, event)
            else:
                color_message(
                    "** Error: unable to recognize url, it should contain '/Artist/' or '/Album/'! **",
                    error_color
                )

    except Exception as e:
        color_message("** Error: Cannot download URL: %s, reason: %s **" % (args.url, str(e)), error_color)
    except KeyboardInterrupt as e:
        color_message("** main: Program interrupted by user, exiting! **", error_color)
        # traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
