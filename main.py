import json
import xml.etree.ElementTree as ET
import os


class Node:
    def __init__(self, name=None, is_root: bool = None, doc=None, attrs=None):
        self.__name = name
        self.__is_root = is_root
        self.__doc__ = doc
        self.__attrs = attrs
        self.__parents = {}
        self.__children = {}
        self.__children_multiplicity = {}
        self.__multiplicity = None

    def get_name(self):
        return self.__name

    def get_attrs(self):
        return self.__attrs

    def get_is_root(self):
        return self.__is_root

    def get_multiplicity(self):
        return self.__multiplicity

    def get_children(self):
        '''
        :return: dict формата: {class_name: object}, object type - Node
        '''
        return self.__children

    def set_parent(self, parent: 'Node'):
        parent_name = parent.get_name()
        if parent_name not in self.__parents:
            self.__parents[parent_name] = parent

    def set_multiplicity(self, multiplicity: range):
        self.__multiplicity = multiplicity

    def set_children_multiplicity(self, target: range, name):
        '''
        Учитываем сколько каких классов наследников потенциально может содержаться в классе родителе
        '''
        self.__children_multiplicity[name] = target

    def add_child(self, child: 'Node'):
        child_name = child.get_name()
        if child_name not in self.__children:
            self.__children[child_name] = [child]
        else:
            self.__children[child_name].append(child)

    def valid_node(self):
        # Проверяем на соответствие source multiplicity
        if self.__children_multiplicity:
            for source, source_range in self.__children_multiplicity.items():
                child_list = self.__children[source]
                if child_list:
                    if len(child_list) not in source_range:
                        return False
        return True


def parse_multiplicity(multiplicity):
    '''
    Функция для формирования range из строки multiplicity
    :param multiplicity: передаем строку вида 0..42 или 1
    :return: range из допустимых значений
    '''
    if multiplicity.isnumeric():
        return range(int(multiplicity), int(multiplicity) + 1)
    else:
        start, end = map(int, multiplicity.split('..'))
        return range(start, end + 1)


# Парсинг input файла
def parse_input_xml(path):
    '''
    :param path: путь до input файла
    :return: root UML диаграммы
    '''
    # Парсим xml
    tree = ET.parse(path)
    root = tree.getroot()

    root_class = None
    # Создаем сами элементы диаграммы
    objects = {}
    for element in root.findall('Class'):
        # Проверка соответствию формата <Class>
        cur_tag_attr = element.attrib
        cur_name = cur_tag_attr['name']
        try:
            # Получаем все атрибуты тега
            cur_is_root = cur_tag_attr['isRoot'] == 'true'
            cur_doc = cur_tag_attr['documentation']
            # Получаем все атрибуты элемента
            cur_elem_attr = []
            for attr in element.findall('Attribute'):
                # Проверяем на наличие атрибута type у <Attribute>
                try:
                    if attr.attrib['type']:
                        cur_elem_attr.append(attr.attrib)
                except:
                    raise Exception('type внутри тега <Attribute>')
        except Exception as e:
            raise Exception(f'Ошибка при создание объекта класса {cur_name}.\n'
                            f'Проверьте соответствие формату атрибута {e}.')
        # Создаем объект класса Node и переносим туда все атрибуты
        new_node = Node(cur_name, cur_is_root, cur_doc, cur_elem_attr if cur_elem_attr else None)
        # Добавляем в виде словаря, чтобы потом проще находить нужный класс для установления реляций
        objects[new_node.get_name()] = new_node
        # Запоминаем root object
        if new_node.get_is_root():
            root_class = new_node
    # Устанавливаем реляции
    for element in root.findall('Aggregation'):
        # Получаем все атрибуты тега
        cur_tag_attr = element.attrib
        cur_source = cur_tag_attr['source']
        cur_target = cur_tag_attr['target']
        # Проверка соответствию формата <Aggregation>
        try:
            cur_multiplicity = parse_multiplicity(cur_tag_attr['sourceMultiplicity'])
        except Exception as e:
            raise Exception(f'Ошибка при установлении агрегаций source={cur_source}, cur_target={cur_target}.\n'
                            f'Проверьте соответствие формату.')
        # Добавляем multiplicity наследников
        objects[cur_target].set_children_multiplicity(cur_multiplicity, cur_source)
        # Добавляем самих наследников для родительского класса
        objects[cur_target].add_child(objects[cur_source])
        # Устанавливаем родителя для класса наследника
        objects[cur_source].set_parent(objects[cur_target])
        # Устанавливаем multiplicity для класса наследника
        objects[cur_source].set_multiplicity(cur_multiplicity)

    return root_class


# Валидация (проходимся по дереву)
def valid_uml(node):
    if not node.valid_node():
        return False
    children = node.get_children()
    for child_list in children.values():
        for child in child_list:
            if not valid_uml(child):
                return False
    return True


# Создание ET для вывода в указанном XML формате
def xml_output(node: Node, xml_item: ET.Element):
    '''
    Для формирования xml файла передаем root UML и root XML
    '''
    # Создаем атрибуты текущего элемента
    if node.get_attrs():
        for attr_dict in node.get_attrs():
            ET.SubElement(xml_item, attr_dict['name']).text = attr_dict['type']
    # Получаем все внутренние теги (всех наследников)
    if node.get_children():
        for name, child_list in node.get_children().items():
            sub_tag = ET.SubElement(xml_item, name)
            if child_list:
                xml_output(child_list[0], sub_tag)
    return None


# Проходимся по всем классам в UML
def json_output(node, result):
    '''
    Сохраняет в переменную result все классы в указанном формате
    '''
    if node.get_is_root():
        result.append(json_format_for_node(node))
    children = node.get_children()
    if children:
        for child_list in children.values():
            # Берем только 1 объект класса если их несколько
            inner_class = child_list[0]
            result.append(json_format_for_node(inner_class))
            json_output(inner_class, result)


# Формируем json для 1 класса
def json_format_for_node(node):
    '''
    Создаем dict нужного формата вывода для одного класса
    '''
    meta_inform = {"class": node.get_name(),
                   "documentation": node.__doc__,
                   "isRoot": node.get_is_root(),
                   }
    # Добавляет target multiplicity если она есть
    if node.get_multiplicity():
        meta_inform["max"] = max(node.get_multiplicity())
        meta_inform["min"] = min(node.get_multiplicity())
    # Добавляем parameters если они есть
    if node.get_attrs():
        meta_inform["parameters"] = node.get_attrs()
    else:
        meta_inform["parameters"] = []
    # Проходимся по всем порожденным классам от данного
    children = node.get_children()
    if children:
        for name, child_list in children.items():
            if child_list:
                meta_inform["parameters"].append({"name": name, "type": "class"})
    return meta_inform


if __name__ == '__main__':
    input_file = rf'input/impulse_test_input.xml'
    output_dir = 'out'
    # Создаем папку с результатами
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    # Парсим файл, получаем root элемент UML диаграммы
    root_class = parse_input_xml(input_file)
    # Проверяем UML на валидность
    if valid_uml(root_class):
        # config.xml
        # Создаем root
        xml_root = ET.Element(root_class.get_name())
        # Вызываем функцию формирования XML файла
        xml_output(root_class, xml_root)
        # Создаем config файл с нужными отступами
        ET.indent(xml_root, space='\t', level=0)
        tree = ET.ElementTree(xml_root)
        tree.write(os.path.join(output_dir, 'config.xml'))

        # meta.json
        result_json = []
        json_output(root_class, result_json)
        with open(os.path.join(output_dir, 'meta.json'), 'w') as file:
            json.dump(result_json, file, indent=4)
