#!/usr/bin/env bash
# The settings of the GitHub repository, applied with gh (make github-settings): run it after making the repository
# again and after making it public. It can be run any number of times. Settings GitHub's free plan gives only to public
# repositories (rulesets, environment reviewers, secret scanning...) are reported as waiting while it is private.
set -euo pipefail

repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
owner=${repo%%/*}
visibility=$(gh api "repos/$repo" --jq .visibility)
echo "$repo ($visibility)"

applied() { echo "  applied: $1"; }
waiting() { echo "  waiting: $1 (on GitHub's free plan only for a public repository)"; }
# try <description> <command...>: applied, or waiting when GitHub refuses it on this plan
try() {
	local what=$1
	shift
	if "$@" > /dev/null 2>&1; then applied "$what"; else waiting "$what"; fi
}

# The repository
gh api -X PATCH "repos/$repo" -F has_wiki=false -F has_projects=false \
	-f description="Builds a Minecraft resource pack of Japanese for children: kana only, and the kanji of each school grade" \
	> /dev/null && applied "description, no wiki, no projects"
gh api -X PUT "repos/$repo/topics" --input - > /dev/null <<'EOF'
{"names": ["minecraft", "resource-pack", "language-pack", "japanese", "kanji"]}
EOF
applied "topics"

# Actions: actions pinned by a commit SHA, only GitHub's own and the one the workflows use; a read-only token by
# default, which may not approve pull requests; approval for every pull request of outside contributors
gh api -X PUT "repos/$repo/actions/permissions" --input - > /dev/null <<'EOF'
{"enabled": true, "allowed_actions": "selected", "sha_pinning_required": true}
EOF
gh api -X PUT "repos/$repo/actions/permissions/selected-actions" --input - > /dev/null <<'EOF'
{"github_owned_allowed": true, "verified_allowed": false,
 "patterns_allowed": ["Kira-NT/mc-publish@*"]}
EOF
gh api -X PUT "repos/$repo/actions/permissions/workflow" --input - > /dev/null <<'EOF'
{"default_workflow_permissions": "read", "can_approve_pull_request_reviews": false}
EOF
applied "Actions: SHA pinning, allowed actions, read-only token"
try "Actions: approval for pull requests of outside contributors" \
	gh api -X PUT "repos/$repo/actions/permissions/fork-pr-contributor-approval" -f approval_policy=all_external_contributors

# Security
try "Dependabot alerts" gh api -X PUT "repos/$repo/vulnerability-alerts"
try "Dependabot security updates" gh api -X PUT "repos/$repo/automated-security-fixes"
try "secret scanning and push protection" gh api -X PATCH "repos/$repo" --input - <<'EOF'
{"security_and_analysis": {"secret_scanning": {"status": "enabled"},
                           "secret_scanning_push_protection": {"status": "enabled"}}}
EOF
try "private vulnerability reporting" gh api -X PUT "repos/$repo/private-vulnerability-reporting"
try "immutable releases" gh api -X PUT "repos/$repo/immutable-releases"

# The environment release (release.yml's jobs that publish): the owner approves, and only from the branch main (a
# release is made by a push to main)
owner_id=$(gh api "users/$owner" --jq .id)
if gh api -X PUT "repos/$repo/environments/release" --input - > /dev/null 2>&1 <<EOF
{"reviewers": [{"type": "User", "id": $owner_id}],
 "deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true}}
EOF
then
	policies="repos/$repo/environments/release/deployment-branch-policies"
	for id in $(gh api "$policies" --jq '.branch_policies[] | select(.name != "main" or .type != "branch") | .id'); do
		gh api -X DELETE "$policies/$id" > /dev/null
	done
	if ! gh api "$policies" --jq '.branch_policies[] | select(.name == "main" and .type == "branch")' | grep -q .; then
		gh api -X POST "$policies" -f name=main -f type=branch > /dev/null
	fi
	applied "environment release: the owner approves, the branch main only"
else
	gh api -X PUT "repos/$repo/environments/release" > /dev/null
	waiting "environment release with a reviewer and the branch main only (made without them for now)"
fi

# Rulesets: main takes changes only through pull requests whose build passed, never force pushed or deleted; tags v*
# are never moved or deleted. Their creation is not limited: release.yml makes the tag of a release with GITHUB_TOKEN,
# and GitHub Actions cannot bypass a ruleset of a user's repository (only an organization's). Administrators may bypass
# both (the owner)
ruleset() {
	local name=$1 body=$2 id
	id=$(gh api "repos/$repo/rulesets" --jq ".[] | select(.name == \"$name\") | .id" 2> /dev/null || true)
	if [ -n "$id" ]; then
		gh api -X PUT "repos/$repo/rulesets/$id" --input - <<< "$body"
	else
		gh api -X POST "repos/$repo/rulesets" --input - <<< "$body"
	fi
}
BYPASS='[{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]'
try "ruleset main" ruleset main "$(cat <<EOF
{"name": "main", "target": "branch", "enforcement": "active", "bypass_actors": $BYPASS,
 "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
 "rules": [{"type": "deletion"}, {"type": "non_fast_forward"},
           {"type": "pull_request", "parameters": {"required_approving_review_count": 0,
            "dismiss_stale_reviews_on_push": false, "require_code_owner_review": false,
            "require_last_push_approval": false, "required_review_thread_resolution": false}},
           {"type": "required_status_checks", "parameters": {"strict_required_status_checks_policy": false,
            "required_status_checks": [{"context": "build"}]}}]}
EOF
)"
try "ruleset release tags" ruleset "release tags" "$(cat <<EOF
{"name": "release tags", "target": "tag", "enforcement": "active", "bypass_actors": $BYPASS,
 "conditions": {"ref_name": {"include": ["refs/tags/v*"], "exclude": []}},
 "rules": [{"type": "update"}, {"type": "deletion"}]}
EOF
)"

echo "Not set here: the variable MODRINTH_PROJECT_ID and the secret MODRINTH_TOKEN of the environment release"
echo "(gh variable set MODRINTH_PROJECT_ID; gh secret set MODRINTH_TOKEN --env release)"
