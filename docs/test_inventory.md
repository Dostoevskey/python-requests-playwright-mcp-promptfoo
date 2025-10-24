# Test Inventory

Staff SDET view of automated coverage across the local Conduit RealWorld stack.

## API Suite (27 tests)

| Test | Coverage |
|------|----------|
| `tests/api/test_articles_api.py::test_article_crud_flow` | End-to-end article create/update/delete with ownership validation |
| `tests/api/test_authentication.py::test_user_registration_and_login` | Token issuance for new users and login flow |
| `tests/api/test_authentication.py::test_user_profile_update` | Authenticated profile updates (bio/password) |
| `tests/api/test_comments.py::test_add_and_retrieve_comments` | Comment create/list/delete |
| `tests/api/test_comments.py::test_unauthorized_comment_deletion` | Permission enforcement on comment deletion |
| `tests/api/test_comments.py::test_comment_on_nonexistent_article` | 404 guard for invalid article slugs |
| `tests/api/test_comments.py::test_multiple_comments_ordering` | Integrity of comment ordering after multiple posts |
| `tests/api/test_comments.py::test_empty_comment_rejection` | Validation rejection for empty comment bodies |
| `tests/api/test_comments.py::test_very_long_comment` | Handling of ~6 KB comment payload |
| `tests/api/test_comments.py::test_comment_with_special_characters` | Unicode/emoji support |
| `tests/api/test_error_handling.py::test_duplicate_user_registration` | Duplicate account collision |
| `tests/api/test_error_handling.py::test_login_with_invalid_credentials` | Error responses for wrong credentials |
| `tests/api/test_error_handling.py::test_unauthorized_article_delete` | Cross-user delete guard |
| `tests/api/test_error_handling.py::test_get_nonexistent_article` | Article not-found handling |
| `tests/api/test_error_handling.py::test_invalid_article_creation_missing_fields` | Validation when required fields are omitted |
| `tests/api/test_error_handling.py::test_article_update_slug_change` | Slug mutation when titles change |
| `tests/api/test_error_handling.py::test_pagination_boundary_cases` | Extremes for limit/offset |
| `tests/api/test_error_handling.py::test_favorite_unfavorite_article` | Favorite/unfavorite workflow |
| `tests/api/test_error_handling.py::test_concurrent_article_creation` | Rapid creation yields distinct slugs |
| `tests/api/test_error_handling.py::test_article_with_special_characters` | Unicode article title/body |
| `tests/api/test_error_handling.py::test_unauthorized_profile_update` | Access control on profile updates |
| `tests/api/test_error_handling.py::test_very_long_article_content` | ~17 KB article body acceptance |
| `tests/api/test_error_handling.py::test_multiple_tags_on_article` | Preservation of long tag lists |
| `tests/api/test_pagination.py::test_articles_pagination` | Default feed pagination |
| `tests/smoke/test_smoke_api.py::test_smoke_can_register_user` | Smoke registration |
| `tests/smoke/test_smoke_api.py::test_smoke_can_login_user` | Smoke login |
| `tests/smoke/test_smoke_api.py::test_smoke_can_create_article` | Smoke article creation |

## UI Suite (4 tests)

| Test | Coverage |
|------|----------|
| `tests/smoke/test_smoke_ui.py::test_smoke_frontend_loads` | Landing page smoke validation |
| `tests/ui/test_articles_ui.py::test_ui_author_can_create_article` | Desktop authoring flow from login to publish |
| `tests/ui/test_articles_ui.py::test_ui_feed_pagination` | Mobile pagination path |
| `tests/ui/test_articles_ui.py::test_ui_route_requires_auth` | Route guard for unauthenticated editor access |

## LLM Suites

| Test | Coverage |
|------|----------|
| `tests/llm/test_article_generation.py::test_local_article_generation` | Dual-model generation (gemma3:4b, deepseek-r1:8b) with judge validation |
| `tests/llm/test_promptfoo_suite.py::test_promptfoo_eval` | Promptfoo-driven evaluation (opt-in via `.enable_promptfoo`) |
| `tests/llm/test_article_quality_audit.py::test_article_quality_audit_strict` | Strict multi-iteration audit with historical attachments |

---

Total tests: **34** (API 27, UI 4, LLM 3). Coverage spans authentication, profile management, article and comment CRUD, pagination/tagging, smoke readiness, UI authoring/pagination/auth guard, and LLM smoke vs. audit validations on local models.
