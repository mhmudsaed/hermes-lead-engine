"""Unit tests: URL classification (careers/about/contact detection)."""
from __future__ import annotations

from lead_engine.url_rules import (
    is_about_url,
    is_careers_url,
    is_contact_url,
    pick_about_link,
    pick_careers_link,
    pick_contact_link,
    same_site,
)


def test_careers_detection():
    assert is_careers_url("https://acme.com/careers")
    assert is_careers_url("https://acme.com/jobs?dept=eng")
    assert is_careers_url("https://acme.com/company/join-us")
    assert is_careers_url("https://acme.com/en/hiring")
    assert not is_careers_url("https://acme.com/about")
    assert not is_careers_url("https://acme.com/")


def test_no_false_positives_on_similar_words():
    # segment-based matching must not fire on substrings
    assert not is_careers_url("https://acme.com/about-jobs-fair-sponsors")
    assert not is_about_url("https://acme.com/about-jobs-fair-sponsors")
    assert not is_contact_url("https://acme.com/blog/contactless-payments")


def test_about_detection():
    assert is_about_url("https://acme.com/about")
    assert is_about_url("https://acme.com/about-us")
    assert is_about_url("https://acme.com/company")
    assert not is_about_url("https://acme.com/careers")


def test_contact_detection():
    assert is_contact_url("https://acme.com/contact")
    assert is_contact_url("https://acme.com/contact-us")
    assert is_contact_url("https://acme.com/support")
    assert not is_contact_url("https://acme.com/about")


def test_same_site_requires_same_host():
    assert same_site("https://acme.com/careers", "acme.com")
    assert not same_site("https://jobs.acme.com/", "acme.com")
    assert not same_site("mailto:hi@acme.com", "acme.com")
    assert not same_site("not a url", "acme.com")


def test_pick_prefers_shortest_same_site():
    links = [
        ("https://acme.com/company/about/careers-and-culture", "Culture"),
        ("https://acme.com/careers", "Careers"),
        ("https://external.com/careers", "Careers"),
    ]
    assert pick_careers_link(links, "acme.com") == "https://acme.com/careers"
    assert pick_careers_link([("https://external.com/careers", "x")], "acme.com") is None
    assert pick_careers_link([], "acme.com") is None


def test_pick_about_and_contact():
    links = [
        ("https://acme.com/", "Home"),
        ("https://acme.com/about-us", "About us"),
        ("https://acme.com/contact", "Contact"),
    ]
    assert pick_about_link(links, "acme.com") == "https://acme.com/about-us"
    assert pick_contact_link(links, "acme.com") == "https://acme.com/contact"
    assert pick_contact_link([("https://acme.com/about-us", "About")], "acme.com") is None
