"""sopel-amputator

Sopel plugin that detects AMP links and finds their canonical forms using AmputatorBot
"""
from __future__ import generator_stop

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
IGNORE_DOMAINS = ["bandcamp.com", "progonlymusic.com", "spotify.com", "youtube.com"]


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
    parts = urlparse(suspected_amp_link)

    if any(map(parts.hostname.endswith, bot.settings.amputator.ignore_domains)):
        LOGGER.info("Skipping link from ignored domain: %s", parts.hostname)
        return plugin.NOLIMIT

    params = {
        'gac': 'true',
        'md': 3,
        'q': suspected_amp_link,
    }

    # Using `params=` with a dict directly means requests will urlencode the query
    # and AmputatorBot API doesn't handle that (April 2024)
    r = requests.get(
        AMPUTATOR_CONVERT_API,
        params='&'.join("%s=%s" % (k,v) for k,v in params.items()),
        headers={'User-Agent': USER_AGENT}
    )

    try:
        r.raise_for_status()
    except Exception:
        LOGGER.info(
            'AmputatorBot API returned an error; ignoring suspected AMP link %r' % suspected_amp_link)
        return plugin.NOLIMIT

    data = r.json()[0]
    if data['canonical']:
        bot.say("{}'s canonical link: {}".format(trigger.nick, data['canonical']['url']))
