# nora_lib

For making and coordinating agents and tools.

# Development

When preparing a PR, make sure you first run the verify script
to confirm the code is buildable, passes type- and formatting-checks,
as well as unit tests.

```bash
cd <project_root>
./verify.sh
```

The script will tell you what's wrong if anything fails.

Update the `version=` field in `setup.py` when you make changes
as part of your changeset.

# Publication

After your PR merges to `main` you will need to publish
the library to public pypi for it to be useable by client applications.

This requires one environment variable to be set, which can be found in
the 1Pass NORA Vault under the secret named "NORA pypi token".

```bash
export AI_NORA_PYPI_TOKEN=<SECRET IN NORA VAULT>
cd <project_root>
git checkout main
git pull origin main
git tag v<YOUR_NEW_VERSION>
git push origin --tags
./publish.sh
```
