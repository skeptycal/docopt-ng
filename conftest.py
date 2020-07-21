import re

try:
    import json
except ImportError:
    import simplejson as json

import pytest

import docopt


pt_version_under_54 = float('.'.join(pytest.__version__.split('.')[0:2])) < 5.4

def pytest_collect_file(path, parent):

    # for pytest version < 5.4, use direct method
    if pt_version_under_54:
        if path.ext == ".docopt" and path.basename.startswith("test"):
            return DocoptTestFile(path, parent)

    # for pytest version >= 5.4, use 'from_parent' constructor
    else:
        if path.ext == ".docopt" and path.basename.startswith("test"):
            return DocoptTestFile.from_parent(parent=parent, fspath=path)



def parse_test(raw):
    raw = re.compile("#.*$", re.M).sub("", raw).strip()
    if raw.startswith('"""'):
        raw = raw[3:]

    for fixture in raw.split('r"""'):
        name = ""
        doc, _, body = fixture.partition('"""')
        cases = []
        for case in body.split("$")[1:]:
            argv, _, expect = case.strip().partition("\n")
            expect = json.loads(expect)
            prog, _, argv = argv.strip().partition(" ")
            cases.append((prog, argv, expect))

        yield name, doc, cases


class DocoptTestFile(pytest.File):
    def collect(self):
        raw = self.fspath.open().read()
        index = 1

        for name, doc, cases in parse_test(raw):
            name = self.fspath.purebasename
            for case in cases:

                # for pytest version < 5.4
                if pt_version_under_54:
                    yield DocoptTestItem("%s(%d)" % (name, index), self, doc, case)

                # for pytest version >= 5.4
                else:
                    test_item = "%s(%d)" % (name, index)
                    kw = {
                        'name': test_item,
                        'doc': doc,
                        'case': case,
                        }
                    yield DocoptTestItem.from_parent(parent=self.parent, **kw)
                index += 1


class DocoptTestItem(pytest.Item):
    def __init__(self, name, parent, doc, case):
        super(DocoptTestItem, self).__init__(name, parent)
        self.doc = doc
        self.prog, self.argv, self.expect = case

    def runtest(self):
        try:
            result = docopt.docopt(self.doc, argv=self.argv)
        except docopt.DocoptExit:
            result = "user-error"

        if self.expect != result:
            raise DocoptTestException(self, result)

    def repr_failure(self, excinfo):
        """Called when self.runtest() raises an exception."""
        if isinstance(excinfo.value, DocoptTestException):
            return "\n".join(
                (
                    "usecase execution failed:",
                    self.doc.rstrip(),
                    "$ %s %s" % (self.prog, self.argv),
                    "result> %s" % json.dumps(excinfo.value.args[1]),
                    "expect> %s" % json.dumps(self.expect),
                )
            )

    def reportinfo(self):
        return self.fspath, 0, "usecase: %s" % self.name


class DocoptTestException(Exception):
    pass
