# How to manual test UMB messaging

In `greenwave/listeners/base.py` comment out lines 299 - 304. Remember to reactivate them
once you are finished.

```
# if _is_decision_unchanged(old_decision, decision):
#     self.app.logger.debug(
#         "Skipped emitting fedora message, decision did not change: %s", decision
#     )
#     self._inc(decision_unchanged_counter.labels(decision_context=decision_context))
#     continue
```

Run podman/docker compose.

```
podman compose up -d
```

Send testing request to UMB so resultdb can acquire it and send it to greenwave.

```
python3 send_umb_message.py --host 127.0.0.1 --port 61612 --topic VirtualTopic.eng.resultsdb.result.new -p resultdb_json.json
```

Check the logs of UMB where you should see whole message that is being sent out.

```
podman compose logs umb
```

Get logs of resultsdb listener

```
podman compose logs resultsdb-listener | tail -n 20
```

For changig code there is no need of rebuilding the container as source code is mounted
into container. If you are experiencing old code rerun the containers
by `podman compose up -d`.