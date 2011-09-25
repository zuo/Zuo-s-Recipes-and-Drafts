#!/usr/bin/env python
# [Python 2.6 compatibile]

"""
smooth_loop.py 0.1.2

Copyright (c) 2010-2011 Jan Kaliszewski (zuo). All rights reserved.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from __future__ import print_function

import collections
import contextlib
import logging
import operator
import optparse
import os.path as osp
import re
import sys
import struct
import traceback
import wave

from numpy import add, arange, array, cos, divide, \
                  fromstring, multiply, pi, resize



# command line interface spec

class Opt(object):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

USAGE_MSG = 'Usage: %prog [options] WAVEFILE(s)\n   or  %prog --help'
VERSION_MSG = __doc__.lstrip().split('\n')[0]
COPYRIGHT_MSG = __doc__.strip()
NO_FILE_MSG = 'no WAVEFILE(s) given'
CANNOT_OVERWRITE_MSG = ('the --filename-suffix SUFFIX value cannot be empty '
                        '(use the --overwrite option instead)')
ARGV_OPT_DEFINITIONS = (
    Opt('--copyright',
        action='store_true',
        help='show copyright information and exit',
    ),
    Opt('-s', '--cf-source',
        default=1.0,
        type='float',
        help='beginning of crossfade-loop mix source-area, in SECONDS',
        metavar='SECONDS',
    ),
    Opt('-l', '--cf-length',
        type='float',
        default=1.5,
        help='crossfade-loop mix length, in SECONDS',
        metavar='SECONDS',
    ),
    Opt('-c', '--cf-cut',
        type='float',
        default=0.1,
        help='length of after-loop area '
             'that will be cut off, in SECONDS',
        metavar='SECONDS',
    ),
    Opt('-e', '--cf-extra',
        type='float',
        default=0.1,
        help='length of extra after-loop area (copied from what is '
             'after crossfade-loop mix source-area), in SECONDS',
        metavar='SECONDS',
    ),
    Opt('-i', '--wave-fade-in',
        type='float',
        default=0.0005,
        help="length of wave's beginning fade-in, in SECONDS",
        metavar='SECONDS',
    ),
    Opt('-f', '--filename-suffix',
        type='string',
        default='.L',
        help='output filename SUFFIX added before .wav extension',
        metavar='SUFFIX',
    ),
    Opt('-o', '--overwrite',
        action='store_true',
        help='overwrite source file(s) (not adding filename suffix)',
    ),
    Opt('-v', '--verbosity',
        type='choice',
        choices=['debug', 'info', 'error', 'quiet'],
        default='info',
        help='verbosity LEVEL',
        metavar='LEVEL',
    ),
)



# other constants

SAMPWIDTHS_TO_TYPECODES = {
    2: 'int16',
    4: 'int32',
}

WAVE_SMPL_CHUNK = ('\x73\x6D\x70\x6C' '\x3C\x00\x00\x00' '\x00\x00\x00\x00'
                   '\x00\x00\x00\x00' '\x00\x00\x00\x00' '\x00\x00\x00\x00'
                   '\x00\x00\x00\x00' '\x00\x00\x00\x00' '\x00\x00\x00\x00'
                   '\x01\x00\x00\x00' '\x18\x00\x00\x00' '\x00\x00\x00\x00'
                   '\x00\x00\x00\x00' '{loop_start}'     '{loop_stop}'
                   '\x00\x00\x00\x00' '\x00\x00\x00\x00')

CHUNK_VALUE_STRUCT_FMT = '<L'



# types

ArrayContainer = collections.namedtuple('ArrayContainer', 'array')
WaveParams = collections.namedtuple('WaveParams', 'nchannels sampwidth '
                                                  'framerate nframes '
                                                  'comptype compname')



# functions

def _make_cosinus_slider(start_x, stop_x, mix_length, nchannels):

    # FIXME: a bug for nchannels != 2...
    one_channel = arange(start_x, stop_x, pi / mix_length)
    slider = array([one_channel for x in xrange(nchannels)]).transpose()
    cos(slider, slider)
    add(slider, 1, slider)
    divide(slider, 2, slider)

    return slider


def do_crossfade_loop_mix(main_wave, side_results, wave_params,
                          opts, log=logging.getLogger()):

    # prepare basic values:

    mix_length = int(opts.cf_length * wave_params.framerate)
    src_start = int(opts.cf_source * wave_params.framerate)
    src_stop = src_start + mix_length
    cut_length = int(opts.cf_cut * wave_params.framerate)
    dest_stop = wave_params.nframes - cut_length
    dest_start = dest_stop - mix_length
    if src_stop > dest_start:
        raise ValueError('The sample is too short for such parameters')

    extra_length = int(opts.cf_extra * wave_params.framerate)
    if src_stop + extra_length > dest_stop:
        raise ValueError('Extra after-loop area is too wide')

    # do crossfade mix:

    fade_in_src = main_wave.array[src_start:src_stop]
    fade_out_place = main_wave.array[dest_start:dest_stop]

    fade_in_slider = _make_cosinus_slider(pi, 2 * pi, mix_length,
                                          wave_params.nchannels)
    fade_out_slider = _make_cosinus_slider(0, pi, mix_length,
                                           wave_params.nchannels)

    fade_in_clipboard = fade_in_src * fade_in_slider  # make fade in
    multiply(fade_out_place, fade_out_slider, fade_out_place)  # make fade out
    add(fade_out_place, fade_in_clipboard, fade_out_place)  # mix

    side_results['loop_start'] = struct.pack(CHUNK_VALUE_STRUCT_FMT, src_stop)
    side_results['loop_stop'] = struct.pack(CHUNK_VALUE_STRUCT_FMT, dest_stop)
    log.debug('Crossfade-loop mix source starts at {0}'.format(src_start))
    log.debug('Loop encloses area: {0} to {1} (length: {2})'
              .format(src_stop, dest_stop, dest_stop - src_stop))

    # resize wave, if needed:

    new_nframes = dest_stop + extra_length
    if new_nframes != wave_params.nframes:
        del fade_in_src, fade_out_place
        main_wave.array.resize((new_nframes, wave_params.nchannels))
        log.debug('Wave resized from {0} to {1}'
                  .format(wave_params.nframes, new_nframes))
    else:
        log.debug('Wave not resized')

    # add extra samples, if needed:

    log.debug('{0} samples cut'.format(cut_length))
    if extra_length:
        (main_wave.array[dest_stop:new_nframes]
        ) = main_wave.array[src_stop:(src_stop + extra_length)]
    log.debug('{0} extra samples'.format(extra_length))

    return main_wave, side_results, wave_params._replace(nframes=new_nframes)


def do_wave_fade_in(main_wave, side_results, wave_params,
                    opts, log=logging.getLogger()):

    fade_in_len = int(opts.wave_fade_in * wave_params.framerate)
    fade_in_place = main_wave.array[0:fade_in_len]
    fade_in_slider = _make_cosinus_slider(pi, 2 * pi, fade_in_len,
                                          wave_params.nchannels)
    multiply(fade_in_place, fade_in_slider, fade_in_place)  # make fade in
    log.debug('Wave fade-in length: {0}'.format(fade_in_len))

    return main_wave, side_results, wave_params


def finalize_processing(main_wave, side_results, wave_params,
                        opts, log=logging.getLogger()):

    result_frames = main_wave.array.tostring()
    to_append_str = WAVE_SMPL_CHUNK.format(**side_results)
    return result_frames, to_append_str, wave_params


def process(src_frames_str, wave_params, opts, log=logging.getLogger()):

    # ArrayContainer engaged to avoid keeping redundant references
    # (they make in-place array.resize() impossible)
    typecode = SAMPWIDTHS_TO_TYPECODES[wave_params.sampwidth]
    main_wave = ArrayContainer(fromstring(src_frames_str, typecode))
    if wave_params.nchannels > 1:
        main_wave.array.resize((wave_params.nframes, wave_params.nchannels))

    side_results = {}

    (main_wave, side_results, wave_params
    ) = do_crossfade_loop_mix(main_wave, side_results, wave_params, opts, log)

    (main_wave, side_results, wave_params
    ) = do_wave_fade_in(main_wave, side_results, wave_params, opts, log)

    (result_frames, to_append_str, wave_params
    ) = finalize_processing(main_wave, side_results, wave_params, opts, log)

    return result_frames, to_append_str, wave_params


def parse_cmdline():

    opt_parser = optparse.OptionParser(usage=USAGE_MSG, version=VERSION_MSG)
    for option in ARGV_OPT_DEFINITIONS:
        default = option.kwargs.get('default')
        if option.kwargs.get('type') == 'choice':
            (option.kwargs['help']
            ) += (' (one of: {0}{1})'
                  .format(', '.join(option.kwargs['choices']),
                          '; default: {0}'.format(default) if default else ''))
        elif default:
            option.kwargs['help'] += ' (default: {0})'.format(default)
        opt_parser.add_option(*option.args, **option.kwargs)
    opts, file_names = opt_parser.parse_args()
    if opts.copyright:
        print(COPYRIGHT_MSG)
        sys.exit(0)
    if not file_names:
        opt_parser.error(NO_FILE_MSG)
    if not opts.filename_suffix:
        opt_parser.error(CANNOT_OVERWRITE_MSG)
    return opts, file_names


def configure_logging(opts):

    verbosity = opts.verbosity.upper()
    if verbosity == 'DEBUG':
        format = ('{0}: %(asctime)s - %(message)s'
                  .format(sys.argv[0]))
    else:
        format = '%(message)s'
        if verbosity == 'QUIET':
            logging.QUIET = sys.maxint
            logging.addLevelName(logging.QUIET, 'QUIET')

    level = getattr(logging, verbosity)
    logging.basicConfig(format=format, level=level)
    return logging.getLogger()


def main():

    opts, file_names = parse_cmdline()
    log = configure_logging(opts)
    try:
        assert file_names
        for i, name in enumerate(file_names):
            log.info('Processing {0}...'.format(name))
            with contextlib.closing(wave.open(name, 'rb')) as wave_read:
                wave_params = WaveParams(*wave_read.getparams())
                src_frames_str = wave_read.readframes(wave_params.nframes)

            (result_frames, to_append_str, wave_params
            ) = process(src_frames_str, wave_params, opts, log)

            if not opts.overwrite:
                base, ext = osp.splitext(name)
                name = ''.join((base, opts.filename_suffix, ext))
            log.debug('Processed. Writing {0}...'.format(name))

            with contextlib.closing(wave.open(name, 'wb')) as wave_write:
                wave_write.setparams(wave_params)
                wave_write.writeframes(result_frames)

            log.debug('Appending loop-information chunk...')

            with open(name, 'ab') as wave_file:
                wave_file.write(to_append_str)

            log.debug('{0} written.'.format(name))

    except BaseException as exc:
        log.error('Error when dealing with {0}: {1}'.format(name, exc))
        log.debug('Debug information:\n----\n%s\n----', traceback.format_exc())
        log.error('Exiting...')
        sys.exit(1)

    else:
        log.info(i and 'All files processed successfully. Exiting...'
                 or 'File processed successfully. Exiting...')


# script

if __name__ == '__main__':
    main()
