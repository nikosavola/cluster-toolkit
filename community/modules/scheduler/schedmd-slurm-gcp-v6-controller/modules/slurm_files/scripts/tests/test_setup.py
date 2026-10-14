# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import shlex
import subprocess

import pytest
from mock import Mock, patch
from common import TstCfg  # needed to import util
import util
import setup


@pytest.mark.parametrize("data_type,altered", [("text", True), ("mediumtext", False), ("", False)])
def test_widen_event_cluster_nodes(data_type, altered):
    lkp = util.Lookup(TstCfg(slurm_cluster_name="m22"))
    with patch.object(setup, "run", return_value=Mock(stdout=f"{data_type}\n")) as run:
        setup.widen_event_cluster_nodes(lkp)
    sql = [shlex.split(c.args[0])[-1] for c in run.call_args_list]
    assert "table_name='m22_event_table'" in sql[0]
    assert len(sql) == (2 if altered else 1)
    if altered:
        assert sql[1].startswith("alter table `m22_event_table` modify `cluster_nodes` mediumtext")


def test_widen_event_cluster_nodes_failure_is_logged():
    lkp = util.Lookup(TstCfg(slurm_cluster_name="m22"))
    err = subprocess.CalledProcessError(1, "mysql")
    with patch.object(setup, "run", side_effect=[Mock(stdout="text\n"), err]), \
            patch.object(setup.log, "exception") as log_exc:
        setup.widen_event_cluster_nodes(lkp)
    log_exc.assert_called_once()


@pytest.fixture
def auto_update_paths(tmp_path):
    service = tmp_path / "dnf-automatic.service"
    service.touch()
    lock = tmp_path / ".rpm.lock"
    lock.touch()
    proc_locks = tmp_path / "locks"
    proc_locks.write_text("1: FLOCK  ADVISORY  WRITE 1 fd:01:1 0 EOF\n")
    with patch.object(setup, "_DNF_AUTOMATIC_SERVICE", service), \
         patch.object(setup, "_DNF_AUTOMATIC_STAMP", tmp_path / "stamp"), \
         patch.object(setup, "_RPM_LOCK", lock), \
         patch.object(setup, "_PROC_LOCKS", proc_locks):
        yield lock, proc_locks


def _auto_update_calls(metadata, active, auto_update_paths):
    def fake_run(cmd, **kwargs):
        return Mock(returncode=0 if active else 3)
    with patch.object(util, "get_metadata", return_value=metadata), \
         patch.object(setup, "run", side_effect=fake_run) as run:
        setup.disable_automatic_updates()
    return [c.args[0] for c in run.call_args_list]


@pytest.mark.parametrize("metadata", ["", "FALSE"])
def test_disable_automatic_updates_needs_metadata(metadata, auto_update_paths):
    assert _auto_update_calls(metadata, True, auto_update_paths) == []


def test_disable_automatic_updates_idle(auto_update_paths):
    calls = _auto_update_calls("TRUE", False, auto_update_paths)
    assert "systemctl disable --now dnf-automatic.timer" in calls
    assert not any("kill" in c for c in calls)


def test_disable_automatic_updates_stops_running_dnf(auto_update_paths):
    calls = _auto_update_calls("TRUE", True, auto_update_paths)
    kills = [c for c in calls if "kill" in c]
    assert kills == [
        "systemctl kill --signal=SIGSTOP dnf-automatic.service",
        "systemctl kill --signal=SIGKILL dnf-automatic.service",
    ]


def test_disable_automatic_updates_lets_transaction_finish(auto_update_paths):
    lock, proc_locks = auto_update_paths
    proc_locks.write_text(f"1: POSIX  ADVISORY  WRITE 4242 fd:01:{lock.stat().st_ino} 0 EOF\n")
    calls = _auto_update_calls("TRUE", True, auto_update_paths)
    kills = [c for c in calls if "kill" in c]
    assert kills == [
        "systemctl kill --signal=SIGSTOP dnf-automatic.service",
        "systemctl kill --signal=SIGCONT dnf-automatic.service",
    ]
