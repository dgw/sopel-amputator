"""sopel-amputator

Sopel plugin that detects AMP links and finds their canonical forms using AmputatorBot
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

import requests

from sopel import plugin, tools
from sopel.config.types import ListAttribute, StaticSection
from sopel.tools.web import trim_url


LOGGER = tools.get_logger('amputator')
USER_AGENT = 'sopel-amputator (https://github.com/dgw/sopel-amputator)'
AMPUTATOR_CONVERT_API = 'https://www.amputatorbot.com/api/v1/convert'
# Substrings borrowed from AmputatorBot:
# https://github.com/KilledMufasa/AmputatorBot/blob/263ff4b3b9c5220f6d0dc3479d8640dca7aafe15/static/static.txt#L8-L9
AMP_KEYWORDS = ["/amp", "amp/", ".amp", "amp.", "?amp", "amp?", "=amp",
                "amp=", "&amp", "amp&", "%%amp", "amp%", "_amp", "amp_"]
IGNORE_DOMAINS = [
    "bandcamp.com",
    "progonlymusic.com",
    "spotify.com",
    "twitter.com",
    "x.com",
    "youtube.com",
]


class AmputatorSection(StaticSection):
    ignore_domains = ListAttribute('ignore_domains', default=IGNORE_DOMAINS)


def setup(bot):
    bot.config.define_section('amputator', AmputatorSection)


def configure(config):
    config.define_section('amputator', AmputatorSection)
    config.amputator.configure_setting(
        'ignore_domains',
        "Enter any domains you want the plugin to ignore (see README):",
    )


def amp_patterns(settings):
    amp_group = '|'.join(map(re.escape, AMP_KEYWORDS))
    amp_link_pattern = 'https?://.*({amp_group}).*'.format(amp_group=amp_group)
    return [re.compile(amp_link_pattern)]


@plugin.url_lazy(amp_patterns)
@plugin.output_prefix('[AMPutator] ')
def amputate(bot, trigger):
    suspected_amp_link = trim_url(trigger.group(0))

    hostname = urlparse(suspected_amp_link).hostname
    ignored = bot.settings.amputator.ignore_domains
    is_ignored_subdomain = \
        any((hostname.endswith('.' + name) for name in ignored))
    is_ignored_domain = \
        is_ignored_subdomain or any((hostname == name for name in ignored))

    if is_ignored_domain:
        LOGGER.info(
            "%s %r matches ignore list; skipping",
            'Subdomain' if is_ignored_subdomain else 'Domain',
            hostname,
        )
        return plugin.NOLIMIT

    params = {
        'gac': 'true',
        'md': 3,
        'q': suspected_amp_link,
    }

    try:
        # Using `params=` with a dict directly means requests will urlencode the query
        # and AmputatorBot API doesn't handle that (April 2024)
        r = requests.get(
            AMPUTATOR_CONVERT_API,
            params='&'.join("%s=%s" % (k,v) for k,v in params.items()),
            headers={'User-Agent': USER_AGENT},
            timeout=(3.0, 10.0),
        )
    except requests.exceptions.ConnectTimeout:
        LOGGER.info('Connection to AmputatorBot API timed out.')
        return plugin.NOLIMIT
    except requests.exceptions.ConnectionError:
        LOGGER.info("Couldn't connect to AmputatorBot API server.")
        return plugin.NOLIMIT
    except requests.exceptions.ReadTimeout:
        LOGGER.info('AmputatorBot API took too long to send data.')
        return plugin.NOLIMIT

    data = None
    try:
        data = r.json()
    except ValueError:
        LOGGER.info('AmputatorBot API returned invalid JSON; aborting.')
        LOGGER.debug('Invalid response data:\n%r', r.content)
        return plugin.NOLIMIT

    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as http_error:
        if data is not None:
            LOGGER.info(
                '%s (%s)',
                data.get('error_message', 'Unknown error'),
                data.get('result_code', '(unknown error type)'),
            )
        else:
            LOGGER.info(
                'AmputatorBot API returned an HTTP error: %s.',
                http_error,
            )
        LOGGER.info(
            'Ignoring suspected AMP link %r due to API error.',
            suspected_amp_link,
        )
        return plugin.NOLIMIT

    # non-error status should be a JSON list of one
    data = data[0]
    if data['canonical']:
        bot.say("{}'s canonical link: {}".format(trigger.nick, data['canonical']['url']))
    else:
        LOGGER.info(
            'No better link found; ignoring suspected AMP URL %r.',
            suspected_amp_link,
        )
