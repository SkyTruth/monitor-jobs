import os
import sys
import glob
from pathlib import Path

my_file = Path("/path/to/file")


class Tif2TilesCleanup:
    email = None

    def main(self, args):
        try:
            # cleanup
            self.remove_empty_logfiles()
            self.remove_warpfiles()
            self.remove_tif_files("tif_files/*")

        except Exception as e:
            print("tif_2_tiles_cleanup error:", str(e), flush=True)

    def remove_empty_logfiles(self):
        try:
            cmd = "find logs/tif_2_tiles -name '*' -size 0 -print0 | xargs -0 rm"
            os.system(cmd)
        except Exception as e:
            # Don't error out, just print the error
            # self.error("cleanup", "error in cleanup", str(e))
            print("error in cleanup", str(e), flush=True)

    def remove_warpfiles(self):
        try:
            files = glob.glob("tif_warp_files/*")
            for f in files:
                os.remove(f)
            # cmd = "find tif_warp_files/*.tif -name '*' -print0 | xargs -0 rm"
            # os.system(cmd)
        except Exception as e:
            # Don't error out, just print the error
            # self.error("cleanup", "error in cleanup", str(e))
            print("error in cleanup", str(e), flush=True)

    def remove_tif_files(self, files):
        try:
            print("removing ", files)
            files = glob.glob(files)
            for f in files:
                # print(os.path.isfile(f), flush=True)
                # my_file = Path("/path/to/file")
                if os.path.isfile(f):
                    print(".", end="", flush=True)
                    os.remove(f)
                elif os.path.isdir(f):
                    self.remove_tif_files(f + "/*")
                    # files = glob.glob(files)
                    # if len(files) == 0:
                    os.rmdir(f)

                # os.remove(f)
            # cmd = "find tif_warp_files/*.tif -name '*' -print0 | xargs -0 rm"
            # os.system(cmd)
        except Exception as e:
            # Don't error out, just print the error
            # self.error("cleanup", "error in cleanup", str(e))
            print("error in cleanup", str(e), flush=True)


# /* ======================================================================= */#
# /*     Commandline Execution
# /* ======================================================================= */#

if __name__ == "__main__":
    it = Tif2TilesCleanup()
    it.main(sys.argv[1:])
