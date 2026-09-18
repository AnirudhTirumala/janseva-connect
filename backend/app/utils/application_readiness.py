"""One definition of "is this application waiting on the citizen?".

The staff queue, its tab counts, and the sidebar badge all need this answer,
and they must never disagree - a badge that says 3 over a list that shows 1 is
how a working queue looks broken.

The Python version already exists as `documents_complete` in
`_document_review_summary`, computed from loaded ORM objects. That cannot
drive a filter: `list_applications` paginates in SQL, so filtering in Python
afterwards would filter the *page*, and any count taken from it would be a
count of the page rather than of the district. This module provides the same
predicate as SQL so the filter and the counts run before OFFSET/LIMIT.

Two subtleties the SQL has to preserve:

* A requirement is satisfied by `requirement_id` OR by a matching
  `document_name` - the denormalised fallback for documents uploaded before
  a scheme's requirement rows were replaced. A plain COUNT of documents would
  over-count instead, because a scheme edit can leave a NULL-requirement row
  beside its replacement.
* Readiness is ANDed with an open status. `_document_review_summary` reads the
  scheme's *current* requirements, with no snapshot of what was required at
  submission, so adding a requirement to a scheme retroactively makes decided
  applications look incomplete. Without the status gate, editing a scheme
  would sweep old approved applications into "awaiting citizen".
"""

from sqlalchemy import and_, exists, not_
from sqlalchemy.orm import Query

from app.models.application import SchemeApplication
from app.models.application_document import ApplicationDocument
from app.models.scheme import SchemeDocumentRequirement

OPEN_STATUSES = ("pending", "under_review")


def _has_unsatisfied_mandatory_document():
    """SQL: at least one mandatory requirement has no matching upload.

    The explicit `.correlate(...)` is load-bearing. Without it SQLAlchemy
    auto-correlation puts `scheme_applications` in the INNER subquery's own
    FROM clause, so `application_documents.application_id =
    scheme_applications.id` joins against every application rather than the
    one being tested - and a document uploaded by an unrelated citizen then
    satisfies this application's requirement. The observable symptom is an
    application showing "0/4 documents uploaded" while the filter reports it
    as complete.
    """
    satisfied = (
        exists()
        .where(
            and_(
                ApplicationDocument.application_id == SchemeApplication.id,
                (ApplicationDocument.requirement_id == SchemeDocumentRequirement.id)
                | (ApplicationDocument.document_name == SchemeDocumentRequirement.name),
            )
        )
        .correlate(SchemeApplication, SchemeDocumentRequirement)
    )
    return exists().where(
        and_(
            SchemeDocumentRequirement.scheme_id == SchemeApplication.scheme_id,
            # `is_mandatory` is nullable with a True default; `== True` skips
            # NULL, matching the Python side's truthiness check.
            SchemeDocumentRequirement.is_mandatory == True,  # noqa: E712
            not_(satisfied),
        )
    )


def awaiting_citizen_clause():
    """Open, and the citizen still owes at least one mandatory document."""
    return and_(
        SchemeApplication.status.in_(OPEN_STATUSES),
        _has_unsatisfied_mandatory_document(),
    )


def apply_queue_view(query: Query, view: str | None) -> Query:
    """Narrow a scoped application query to one queue view.

    "actionable"       - everything except the awaiting-citizen rows, so the
                         default queue only holds work an officer can do.
    "awaiting_citizen" - exactly those rows, so they stay reachable.
    anything else      - untouched.
    """
    if view == "awaiting_citizen":
        return query.filter(awaiting_citizen_clause())
    if view == "actionable":
        return query.filter(not_(awaiting_citizen_clause()))
    return query
