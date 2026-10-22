"""The prompt registry: a changed prompt must carry a new version and a changelog line."""
from app.services import prompts


def test_every_prompt_is_registered_with_a_matching_changelog_tail() -> None:
    for name, p in prompts.REGISTRY.items():
        assert p.name == name
        log = prompts.CHANGELOG[name]
        version, digest, _date, note = log[-1]
        assert version == p.version, f"{name}: version {p.version} but changelog ends at {version}"
        assert digest == p.hash, (f"{name} {p.version}: text changed (hash {p.hash}, changelog says {digest}). "
                                  f"Bump the version and add a changelog line.")
        assert note.strip()


def test_changelog_versions_are_unique_and_ordered() -> None:
    for name, log in prompts.CHANGELOG.items():
        versions = [v for v, *_ in log]
        assert versions == sorted(set(versions), key=lambda v: int(v[1:])), f"{name}: {versions}"
        digests = [h for _, h, *_ in log]
        assert len(set(digests)) == len(digests), f"{name}: repeated hash"


def test_ref_pins_version_and_hash() -> None:
    p = prompts.Prompt("x", "v3", "hello {name}")
    assert p.ref == f"v3 ({prompts.content_hash('hello {name}')})"
    assert p.format(name="bob") == "hello bob"


def test_prompts_format_with_their_parameters() -> None:
    assert "some" in prompts.INTERPRET.format(some="some")
    assert "Chinese" in prompts.VISION.format(lang="Chinese", some="若干")
    assert "English" in prompts.AGENT.format(lang="English")
    assert "{" not in prompts.ANSWER.text  # answer takes no parameters
