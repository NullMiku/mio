## Summary

Briefly describe what this PR changes.

## Motivation

Why is this change needed?

What problem does it solve, or what does it improve?

## Changes

List the main changes made in this PR.

-
-
-

## Related Issues (Optional)

Closes #

Leave this section empty if there is no related issue.

**Opening an Issue before submitting a PR is not required.**

## Testing

Describe the tests you actually ran.

| Test / Command | Platform | Result |
|---|---|---|
| `mio test ...` | | PASS / FAIL / SKIP / NOT_RUN |
| Additional tests (if applicable) | | PASS / FAIL / SKIP / NOT_RUN |

Please distinguish between:

- **PASS:** Executed and passed.
- **FAIL:** Executed and failed.
- **SKIP:** Intentionally skipped, with a reason.
- **NOT_RUN:** Not executed.

Do not report skipped or unexecuted tests as passing.

### Independent Verification (If Applicable)

For changes involving the compiler core, AOT, ABI, runtime, GC, or other critical functionality, describe any independent verification performed.

External tools and other programming languages may be used for cross-validation.

Mio's native testing framework remains the preferred primary testing method.

## Compatibility and Architecture (If Applicable)

Does this change affect any of the following?

- [ ] Language syntax or semantics
- [ ] Type system
- [ ] Compiler or AOT backend
- [ ] ABI or object layout
- [ ] Runtime or GC
- [ ] Standard library
- [ ] Platform compatibility

If applicable, briefly describe the impact.

Mio's formal Core and standard library implementations should remain written in Mio. Other languages may be used for testing and cross-validation.

## Known Limitations (Optional)

Are there any known limitations, unimplemented features, or tests that could not be run?

Please describe them here.

## Notes for Reviewers (Optional)

Anything else the maintainers should know?

---

Thanks for contributing to Mio! 💙

We welcome different implementation ideas and technical approaches.

The maintainers make the final merge decisions based on correctness, compatibility, maintainability, and Mio's overall development direction.

Passing tests is important, but it does not automatically guarantee that a PR will be merged.

Thoughtful contributions are always appreciated, even when further discussion or changes are needed.
