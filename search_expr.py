class QueryBuilder:
    """Builds a complex query string from a configuration dictionary."""

    def __init__(self, config: dict):
        """Initializes the builder with a configuration."""
        self.config = config

    def build(self) -> str:
        """Assembles and returns the final query string from the config."""

        # Create a quick-access map of field rules from the "to_be" list
        positive_rules_map = {}
        for rule in self.config.get("to_be", []):
            if "field" in rule:
                positive_rules_map[rule["field"]] = rule.get("logic", {})
            elif "date" in rule:
                # Handle date as a special case
                date_logic = rule["date"]
                if date_logic.get("ranges"):
                    date_range = date_logic["ranges"][0]
                    positive_rules_map["date"] = (
                        f"date:[{date_range['from']} TO {date_range['to']}]"
                    )

        grouped_queries = []
        groups_config = self.config.get("groups", {})
        for group in groups_config:
            # For each group, create a flat list of all its conditions
            all_group_parts = []

            for field_name in group:
                rule_logic = positive_rules_map.get(field_name)
                if not rule_logic:
                    continue

                # Handle the special case for a pre-formatted date string
                if field_name == "date" and isinstance(rule_logic, str):
                    all_group_parts.append(rule_logic)
                    continue

                for kw in rule_logic.get("and", []):
                    all_group_parts.append(f'{field_name}:"{kw}"')
                for kw in rule_logic.get("or", []):
                    all_group_parts.append(f'{field_name}:"{kw}"')
                for kw in rule_logic.get("alone", []):
                    all_group_parts.append(f'{field_name}:"{kw}"')

            if not all_group_parts:
                continue

            # Join all parts for the group with OR
            joined_group = " OR ".join(all_group_parts)

            if len(all_group_parts) > 1:
                grouped_queries.append(f"({joined_group})")
            else:
                grouped_queries.append(joined_group)

        negative_rules = self.config.get("not_to_be", [])
        not_queries = []
        for rule in negative_rules:
            field_name = rule.get("field")
            logic = rule.get("logic", {})
            if field_name and logic.get("alone"):
                not_queries.extend(f'NOT {field_name}:"{kw}"' for kw in logic["alone"])

        final_parts = grouped_queries + not_queries
        return " AND ".join(filter(None, final_parts))


