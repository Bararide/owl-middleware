from typing import Dict, Any, List, Optional

import valito


class HanaValidator:
    @staticmethod
    def validate(data: Dict[str, Any]) -> bool:
        try:
            person = valito.create_person(data)
            return valito.validate_person(person)
        except Exception as e:
            return False

    @staticmethod
    def validate_detailed(data: Dict[str, Any]) -> List[str]:
        try:
            person = valito.create_person(data)
            return valito.validate_person_detailed(person)
        except Exception as e:
            return [f"Validation error: {str(e)}"]

    @staticmethod
    def create_validated_person() -> Optional[valito.Person]:
        print(dir(valito))
