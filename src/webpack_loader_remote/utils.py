import logging
import boto3
from django.conf import settings

from .loader import WebpackLoaderRemote

_loaders = {}


def get_loader(config_name):
    if config_name not in _loaders:
        _loaders[config_name] = WebpackLoaderRemote(config_name)
    return _loaders[config_name]


def _filter_by_extension(bundle, extension):
    """Return only files with the given extension"""
    for chunk in bundle:
        if chunk["name"].endswith(".{0}".format(extension)):
            yield chunk


def _get_bundle(bundle_name, extension, config):
    bundle = get_loader(config).get_bundle(bundle_name)
    if extension:
        bundle = _filter_by_extension(bundle, extension)
    return bundle


def get_files(bundle_name, extension=None, config="DEFAULT"):
    """Returns list of chunks from named bundle"""
    return list(_get_bundle(bundle_name, extension, config))


def script_tag(src, attrs):
    return '<script type="text/javascript" src="{0}" {1}></script>'.format(src, attrs)


def link_tag(href, attrs):
    return '<link type="text/css" href="{0}" rel="stylesheet" {1}/>'.format(href, attrs)


def get_presigned_url(
    file_name,
    bucket_name,
    prefix=None,
    expiration=3600,
    access_key=None,
    secret_key=None,
    config_name="DEFAULT",
):
    if access_key is None and secret_key is None:
        loader = get_loader(config_name)
        access_key = loader.config["AWS_ACCESS_KEY"]
        secret_key = loader.config["AWS_SECRET_KEY"]

    client = boto3.client(
        "s3", aws_access_key_id=access_key, aws_secret_access_key=secret_key
    )

    if prefix is None:
        object_name = file_name
    else:
        object_name = "{}/{}".format(prefix, file_name)

    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": object_name},
            ExpiresIn=expiration,
        )

    except boto3.ClientError as exc:
        logging.error(exc)
        return None


def get_as_presigned_tags(
    bundle_name,
    bucket_name,
    prefix=None,
    expiration=None,
    extension=None,
    config="DEFAULT",
    attrs="",
):
    bundle = _get_bundle(bundle_name, extension, config)

    tags = []

    for chunk in bundle:
        file_name = chunk["name"]
        presigned_url = get_presigned_url(
            file_name, bucket_name, prefix, expiration, config
        )

        if file_name.endswith((".js", ".js.gz")):
            tags.append(script_tag(presigned_url, attrs))
        elif file_name.endswith((".css", ".css.gz")):
            tags.append(link_tag(presigned_url, attrs))

    return tags


def get_as_tags(bundle_name, extension=None, config="DEFAULT", attrs=""):
    """
    Get a list of formatted <script> & <link> tags for the assets in the
    named bundle.

    :param bundle_name: The name of the bundle
    :param extension: (optional) filter by extension, eg. 'js' or 'css'
    :param config: (optional) the name of the configuration
    :return: a list of formatted tags as strings
    """

    bundle = _get_bundle(bundle_name, extension, config)
    tags = []
    for chunk in bundle:
        if chunk["name"].endswith((".js", ".js.gz")):
            tags.append(
                ('<script type="text/javascript" src="{0}" {1}></script>').format(
                    chunk["url"], attrs
                )
            )
        elif chunk["name"].endswith((".css", ".css.gz")):
            tags.append(
                ('<link type="text/css" href="{0}" rel="stylesheet" {1}/>').format(
                    chunk["url"], attrs
                )
            )
    return tags


def get_static(asset_name, config="DEFAULT"):
    """
    Equivalent to Django's 'static' look up but for webpack assets.

    :param asset_name: the name of the asset
    :param config: (optional) the name of the configuration
    :return: path to webpack asset as a string
    """
    return "{0}{1}".format(
        get_loader(config)
        .get_assets()
        .get("publicPath", getattr(settings, "STATIC_URL")),
        asset_name,
    )
