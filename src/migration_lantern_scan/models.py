from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Locale(StrEnum):
    EN = "en"
    JA = "ja"


class Provider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class Severity(StrEnum):
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SourceEvidence(StrictModel):
    title: str = Field(min_length=1)
    url: str
    checked_on: date

    @model_validator(mode="after")
    def official_https_only(self) -> SourceEvidence:
        parsed = urlsplit(self.url)
        host = parsed.hostname
        official = host in {
            "developers.openai.com",
            "platform.openai.com",
            "platform.claude.com",
            "docs.anthropic.com",
        }
        official_openai_github = host == "github.com" and (
            parsed.path == "/openai/openai-python"
            or parsed.path.startswith("/openai/openai-python/")
        )
        if parsed.scheme != "https" or not (official or official_openai_github):
            raise ValueError("evidence must be an approved provider-owned HTTPS URL")
        return self


class PublicRule(StrictModel):
    rule_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]+$")
    provider: Provider
    category: Literal["model", "endpoint", "sdk_syntax"]
    title_en: str = Field(min_length=1)
    title_ja: str = Field(min_length=1)
    deprecated_target: str = Field(min_length=1)
    recommended_target: str = Field(min_length=1)
    replacement_at_announcement: str | None = None
    migration_note_en: str | None = None
    migration_note_ja: str | None = None
    announced_on: date | None = None
    deadline: date | None = None
    severity: Severity
    evidence: list[SourceEvidence] = Field(min_length=1)
    match_kind: Literal["model_argument", "qualified_call"]
    call_paths: list[str] = Field(min_length=1)
    call_match: Literal["suffix", "exact"] = "suffix"
    receiver_names: list[str] = Field(default_factory=list)
    keyword: str | None = None
    deprecated_values: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_match_shape(self) -> PublicRule:
        if self.match_kind == "model_argument":
            if not self.keyword or not self.deprecated_values:
                raise ValueError("model_argument rules need keyword and deprecated_values")
            if self.deprecated_target not in self.deprecated_values:
                raise ValueError("deprecated_target must be one of deprecated_values")
        elif self.keyword is not None or self.deprecated_values:
            raise ValueError("qualified_call rules cannot define model keyword/value fields")
        return self


class PublicRegistry(StrictModel):
    schema_version: Literal["1.0"]
    verified_on: date
    rules: list[PublicRule] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_rule_ids(self) -> PublicRegistry:
        ids = [rule.rule_id for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("rule IDs must be unique")
        return self


class Finding(StrictModel):
    finding_id: str
    rule_id: str
    provider: Provider
    category: Literal["model", "endpoint", "sdk_syntax"]
    severity: Severity
    confidence: Literal["high", "review"]
    path: str
    line: int = Field(ge=1)
    column: int = Field(ge=1)
    call: str
    matched_value: str
    deprecated_target: str
    recommended_target: str
    replacement_at_announcement: str | None
    migration_note: str | None
    announced_on: date | None
    deadline: date | None
    lifecycle_status: Literal["scheduled", "retired", "legacy-no-deadline"]
    evidence: list[SourceEvidence]


class ScanIssue(StrictModel):
    path: str
    kind: Literal[
        "read_error",
        "parse_error",
        "dynamic_value",
        "limit_exceeded",
        "unsafe_path",
    ]
    detail: str
    line: int | None = None


class ScanReport(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    tool_version: str
    generated_at: datetime
    locale: Locale
    target: str
    as_of: date
    registry_verified_on: date
    registry_sha256: str
    files_scanned: int = Field(ge=0)
    findings: list[Finding]
    issues: list[ScanIssue]
