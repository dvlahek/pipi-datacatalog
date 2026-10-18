import pytest

from app.security.url_policy import UnsafeResourceURL, validate_external_resource_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/data.csv",
        "http://10.0.0.5/data.csv",
        "http://192.168.1.10/data.csv",
        "http://169.254.169.254/latest/meta-data/",
        "http://localhost/data.csv",
        "file:///etc/passwd",
        "ftp://example.com/data.csv",
        "https://user:password@example.com/data.csv",
    ],
)
def test_unsafe_resource_urls_are_rejected(url: str) -> None:
    with pytest.raises(UnsafeResourceURL):
        validate_external_resource_url(url, allowed_ports={80, 443})


def test_public_https_ip_is_accepted_without_dns_dependency() -> None:
    assert (
        validate_external_resource_url(
            "https://1.1.1.1/data.csv", allowed_ports={80, 443}
        )
        == "https://1.1.1.1/data.csv"
    )


def test_unapproved_port_is_rejected_before_dns_lookup() -> None:
    with pytest.raises(UnsafeResourceURL):
        validate_external_resource_url(
            "https://example.com:8443/data.csv", allowed_ports={80, 443}
        )
