import os
import beets.importer as importer
from beets.ui.commands import AlbumChange
from beets.library import Library
from beets import config, plugins
from beets.autotag import Recommendation

from audiobookbay import add_label_to_torrent, get_torrents
from utils import custom_logger

logger = custom_logger(__name__)

plugins.load_plugins(str(config["plugins"]).split(" "))
# logger.info(config)

BEETS_DIR = os.getenv("BEETSDIR", "/config")
BEETS_INPUT_PATH = os.getenv("BEETS_INPUT_PATH", "/beetsinput")
BEETS_COMPLETE_LABEL = os.getenv("BEETS_COMPLETE_LABEL", "beets")
BEETS_ERROR_LABEL = os.getenv("BEETS_ERROR_LABEL", "beetserror")
ADMIN_USER = {"role": "admin"}

lib = Library(os.path.join(BEETS_DIR, "library.db"), directory=config["directory"].get())

class ProgrammaticImportSession(importer.ImportSession):
    def summary_judgement(self, rec):
        """Determines whether a decision should be made without even asking
        the user. This occurs in quiet mode and when an action is chosen for
        NONE recommendations. Return None if the user should be queried.
        Otherwise, returns an action. May also print to the console if a
        summary judgment is made.
        """
        if rec == Recommendation.strong:
            return importer.action.APPLY
        if config["import"]["quiet"]:
            action = importer.action.SKIP
            if rec != Recommendation.strong:
                action = config["import"]["quiet_fallback"].as_choice(
                    {
                        "skip": importer.action.SKIP,
                        "asis": importer.action.ASIS,
                    }
                )
        elif config["import"]["timid"]:
            return None
        elif rec == Recommendation.none:
            action = config["import"]["none_rec_action"].as_choice(
                {
                    "skip": importer.action.SKIP,
                    "asis": importer.action.ASIS,
                    "ask": None,
                }
            )
        else:
            return None

        if action == importer.action.SKIP:
            logger.info("Skipping.")
        elif action == importer.action.ASIS:
            logger.info("Using as-is.")
        return action

    def show_change(self, cur_artist, cur_album, match):
        # print(cur_artist, cur_album, match)
        pass

    def choose_match(self, task):
        results = plugins.send(
            "import_task_before_choice", session=self, task=task
        )
        # actions = [action for action in results if action]
        action = self.summary_judgement(task.rec)
        if action == importer.action.APPLY:
            match = task.candidates[0]
            self.show_change(task.cur_artist, task.cur_album, match)
            return match
        # elif action is not None:
            # return action
        return None

    def choose_item(self, task):
        return

    def resolve_duplicate(self, task, found_duplicates):
        return

    def should_resume(self, path):
        return

    def _get_choices(self, task):
        return

def getFolders(torrent):
    folders = set()
    for file in torrent.get("files"):
        folders.add(os.path.join(BEETS_INPUT_PATH, file.get("name").split("/")[0]))
    return list(folders)

def autoimport():
    torrents = get_torrents(ADMIN_USER)
    torrents = [torrent for torrent in torrents if ("audiobook" in torrent.get("labels") and BEETS_COMPLETE_LABEL not in torrent.get("labels") and BEETS_ERROR_LABEL not in torrent.get("labels"))]
    if not torrents:
        logger.warn("No torrents found")
        return
    logger.info(f"Found {len(torrents)} torrents")
    for torrent in torrents:
        try:
            logger.info(f"Processing {torrent['name']}")
            folders = getFolders(torrent)
            #TODO: its going to music folder, see why and change folderpath
            session = ProgrammaticImportSession(
                lib,
                loghandler=logger,
                paths=folders,
                query=None
            )
            session.run()
            add_label_to_torrent(torrent.get("id"), ADMIN_USER, BEETS_COMPLETE_LABEL)
        except Exception as e:
            logger.exception(f"Import failed: {e}")
            continue
