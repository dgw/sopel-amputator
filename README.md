# sopel-amputator

Sopel plugin that detects AMP links and finds their canonical forms using
[AmputatorBot](https://www.amputatorbot.com/)

## Installing

Releases are hosted on PyPI, so after installing Sopel, all you need is `pip`:

```shell
$ pip install sopel-amputator
```

## Configuring

The easiest way to configure `sopel-amputator` is via Sopel's
configuration wizard—simply run `sopel-plugins configure amputator`
and enter the values for which it prompts you.

Individual settings are described below.

### `ignore_domains`

This is a list of hostnames which `sopel-amputator` will ignore, even if they
match one of the common AMP substrings it looks for. By default it contains a
set of ignored domains from the AmputatorBot project.

Setting this value _overrides_ the default, so make sure to also enter any
entries that you would like to keep from the default list.
