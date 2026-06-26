# Hook PyMySQL as MySQLdb for TiDB/MySQL support
try:
    import pymysql
    pymysql.install_as_MySQLdb()
    pymysql.version_info = (2, 2, 1, "final", 0)
    pymysql.__version__ = "2.2.1"
except ImportError:
    pass
