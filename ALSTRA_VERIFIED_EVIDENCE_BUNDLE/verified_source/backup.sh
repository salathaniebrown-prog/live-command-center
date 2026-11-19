#!/bin/bash
cd ~/storage/shared/Factory
tar -czf backups/$(date +%Y-%m-%d_%H-%M).tar.gz projects/ scripts/
# keep last 20
ls -t backups/*.tar.gz | tail -n +21 | xargs rm -f
