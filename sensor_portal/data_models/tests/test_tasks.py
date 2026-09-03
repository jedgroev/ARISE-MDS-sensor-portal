from datetime import timedelta
from unittest.mock import patch

import pytest
from archiving.models import Archive
from data_models.factories import (DataFileFactory, DeploymentFactory,
                                   ProjectFactory)
from data_models.models import DataFile
from data_models.tasks import clean_all_files
from django.utils import timezone as djtimezone


def _archived_file(project, age_days):
    """Create an archived, locally stored file for `project`, last modified `age_days` ago."""
    deployment = DeploymentFactory(
        deployment_ID=f"{project.name}_deployment", project=[project])
    # Explicit file_name: the factory uses get_or_create on (file_name, file_format).
    data_file = DataFileFactory(
        file_name=f"{project.name}_file", deployment=deployment,
        archived=True, local_storage=True)
    # modified_on is auto_now, so it has to be set with an update.
    DataFile.objects.filter(pk=data_file.pk).update(
        modified_on=djtimezone.now() - timedelta(days=age_days))
    return data_file


@pytest.mark.django_db
def test_clean_all_files_uses_each_projects_own_clean_time():
    """
    Test: clean_all_files must only remove a project's own files once that project's
    clean_time has passed. A short clean_time on one project must not cause files of
    other projects to be removed.
    """
    archive = Archive.objects.create(
        name="test_archive", username="user", password="pw",
        address="archive.example", root_folder="/")
    short_project = ProjectFactory(
        name="short", clean_time=10, archive=archive)
    long_project = ProjectFactory(name="long", clean_time=90, archive=archive)

    short_file = _archived_file(short_project, age_days=30)
    long_file = _archived_file(long_project, age_days=30)

    with patch.object(DataFile, "clean_file", autospec=True) as mock_clean:
        clean_all_files()

    cleaned_pks = {call.args[0].pk for call in mock_clean.call_args_list}
    assert short_file.pk in cleaned_pks
    assert long_file.pk not in cleaned_pks
