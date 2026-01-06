#!/bin/bash
DRY_RUN=0
JOURNAL=0
RESTART=""
EDIT=0
STATUS=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--dry-run)
      DRY_RUN=1
      ;;
    -j|--journal)
      JOURNAL=1
      ;;
    -e|--edit)
      EDIT=1
      ;;
    -s|--status)
      STATUS=1
      ;;
    -r|--restart)
      RESTART=1
      ;;
    *)
      echo "Unbekannte Option: $1"
      exit 1
      ;;
  esac
  shift
done

if [ "$DRY_RUN" -eq 1 ]; then
    echo "Dry run autostart service"
    exit 0
fi

if [ "$RESTART" -eq 1 ]; then
    echo "Restart autostart service"
    sudo systemctl restart autostart
    exit 0
fi
 
if [ "$JOURNAL" -eq 1 ]; then
    echo "show curret autostart service journal"
    journalctl -u autostart.service -f
    exit 0
fi
 
if [ "$EDIT" -eq 1 ]; then
    echo "edit autostart service"
    sudo nano /etc/systemd/system/autostart.service
    exit 0
fi
 
if [ "$STATUS" -eq 1 ]; then
    echo "get autostart service status"
    sudo systemctl status autostart.service
    exit 0
fi

