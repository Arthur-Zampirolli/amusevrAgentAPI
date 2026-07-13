import xmltodict

class XMLController:
    xml_dict: dict
    xml_data: str
    def __init__(self, xml_data: str):
        self.xml_data = xml_data
        self.xml_dict = xmltodict.parse(xml_data)

    def _ensure_list(self, data, key):
        """Função auxiliar para garantir que uma chave do xmltodict venha sempre como lista."""
        if key not in data or data[key] is None:
            return []
        if isinstance(data[key], list):
            return data[key]
        return [data[key]]

    def add_property(self, payload: str, scene_id: str):
        #temp_dict = None
        #xml_valido = ''
        xml_valido = f"<root>{payload}</root>"
        temp_dict = xmltodict.parse(xml_valido)
        try:
            root_data = temp_dict['root']
        except NameError:
            root_data = temp_dict
        scenes = self.xml_dict['multisel']['body']['scene']
        if isinstance(scenes, dict):
            scenes = [scenes]

        for scene in scenes:
            if scene['@id'] == scene_id:
                has_changes = False

                if 'effect' in root_data:
                    if 'effect' not in scene:
                        scene['effect'] = []

                    current_scene_effects = self._ensure_list(scene, 'effect')
                    incoming_effects = self._ensure_list(root_data, 'effect')

                    for new_effect in incoming_effects:
                        existing_effect = next((e for e in current_scene_effects if e['@id'] == new_effect['@id']),
                                               None)

                        if existing_effect:
                            existing_effect.update(new_effect)
                        else:
                            # Insere se não existir
                            current_scene_effects.append(new_effect)
                        has_changes = True

                    scene['effect'] = current_scene_effects

                if 'relation' in root_data:
                    if 'relation' not in scene:
                        scene['relation'] = []

                    current_scene_relations = self._ensure_list(scene, 'relation')
                    incoming_relations = self._ensure_list(root_data, 'relation')

                    for new_relation in incoming_relations:
                        existing_relation = next(
                            (r for r in current_scene_relations if r['@id'] == new_relation['@id']), None)

                        if existing_relation:
                            existing_relation.update(new_relation)
                        else:
                            current_scene_relations.append(new_relation)
                        has_changes = True

                    scene['relation'] = current_scene_relations


                if has_changes:
                    self.xml_data = xmltodict.unparse(self.xml_dict, pretty=True)
                    print("XML atualizado com sucesso!")
                break

    def set_xml_dict(self, xml_data: str):
        self.xml_data = xml_data
        self.xml_dict = xmltodict.parse(xml_data)
    def get_xml_dict(self):
        return self.xml_dict
    def get_xml_data(self):
        return self.xml_data