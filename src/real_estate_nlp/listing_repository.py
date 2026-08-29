"""Database access for executable listing filters."""

from __future__ import annotations

import os


class ListingRepository:
    """Fetch listing IDs that satisfy the supported structured filters."""

    FILTERS = {
        "city": ("L_City", "="),
        "price_min": ("L_SystemPrice", ">="),
        "price_max": ("L_SystemPrice", "<="),
        "beds": ("L_Keyword2", "="),
        "beds_min": ("L_Keyword2", ">="),
        "beds_max": ("L_Keyword2", "<="),
        "baths": ("LM_Dec_3", "="),
        "baths_min": ("LM_Dec_3", ">="),
        "baths_max": ("LM_Dec_3", "<="),
        "sqft": ("LM_Int2_3", "="),
        "sqft_min": ("LM_Int2_3", ">="),
        "sqft_max": ("LM_Int2_3", "<="),
    }

    def __init__(self, connection_factory=None, **connection_kwargs):
        self.connection_factory = connection_factory
        self.connection_kwargs = connection_kwargs

    @classmethod
    def from_env(cls):
        return cls(
            host=os.getenv("MYSQL_HOST", "127.0.0.1"),
            port=int(os.getenv("MYSQL_PORT", "3307")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", "root"),
            database=os.getenv("MYSQL_DATABASE", "real_estate"),
            connection_timeout=int(os.getenv("MYSQL_CONNECT_TIMEOUT", "5")),
        )

    def find_candidate_ids(self, hard_filters):
        sql, params = self.build_query(hard_filters)
        connection = self._connect()
        cursor = connection.cursor()
        try:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        finally:
            cursor.close()
            connection.close()
        return {self._listing_id(row) for row in rows}

    def build_query(self, hard_filters):
        conditions = []
        params = []
        for key, (column, operator) in self.FILTERS.items():
            if key in hard_filters:
                conditions.append(f"{column} {operator} %s")
                params.append(hard_filters[key])

        sql = "SELECT L_ListingID FROM rets_property"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        return sql, params

    def _connect(self):
        if self.connection_factory is not None:
            return self.connection_factory()

        import mysql.connector

        return mysql.connector.connect(**self.connection_kwargs)

    @staticmethod
    def _listing_id(row):
        if isinstance(row, dict):
            return str(row.get("listing_id") or row.get("L_ListingID") or "")
        return str(row[0])
