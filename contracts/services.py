# contracts/services.py
import os
import io
import re
from django.conf import settings
from django.utils import timezone
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH


class ContractWordGenerator:
    """Генератор договора из шаблона Word с подстановкой данных по плейсхолдерам"""
    
    def __init__(self, contract):
        self.contract = contract
        self.template_path = os.path.join(
            settings.BASE_DIR,
            'templates',
            'documents',
            'Договор об образовании между ДОУ и родителями.docx'
        )
    
    def generate(self):
        """Генерирует договор из шаблона Word"""
        if not os.path.exists(self.template_path):
            raise FileNotFoundError(f"Шаблон не найден: {self.template_path}")
        
        doc = Document(self.template_path)
        context = self._get_context_data()
        
        self._fill_document(doc, context)
        
        # Сохраняем в буфер
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        return buffer
    
    def _get_context_data(self):
        """Подготовка всех данных для подстановки в шаблон"""
        contract = self.contract
        parent = contract.parent
        child = contract.child
        
        # Паспортные данные родителя
        passport_series_number = ''
        if parent and parent.passport_series and parent.passport_number:
            passport_series_number = f"{parent.passport_series} {parent.passport_number}"
        
        # Адрес регистрации
        registration_address = ''
        if parent and parent.registration_address:
            registration_address = parent.registration_address
        elif contract.application and contract.application.registration_address:
            registration_address = contract.application.registration_address
        
        # Склонение суммы в пропись
        def number_to_words(num):
            try:
                rub = int(float(num))
                return f"{rub} рублей 00 копеек"
            except:
                return "0 рублей 00 копеек"
        
        # Данные заявления
        application_number = ''
        if contract.application:
            application_number = str(contract.application.application_number)[:8]
        
        # Формируем словарь со всеми плейсхолдерами из шаблона
        context = {
            # Основная информация
            'номер_договора': contract.contract_number,
            'дата_регистрации': contract.registration_date.strftime('%d.%m.%Y'),
            
            # Данные ребенка
            'физ_ребенка': contract.child_full_name,
            'дата_рождения_ребенка': contract.child_birth_date.strftime('%d.%m.%Y'),
            
            # Данные родителя
            'физ_родителя': parent.user.get_full_name() if parent else '',
            'паспорт_серия_номер': passport_series_number,
            'паспорт_выдан': parent.passport_issued_by if parent else '',
            'дата_выдачи_паспорта': parent.passport_issue_date.strftime('%d.%m.%Y') if parent and parent.passport_issue_date else '',
            'адрес_регистрации': registration_address,
            
            # Условия договора
            'название_группы': contract.group_name,
            'срок_обучения': contract.study_period,
            'основание': contract.basis_documents,
            
            # Финансовые данные
            'родительская_плата': f"{contract.parent_fee:.2f}",
            'родительская_плата_прописью': number_to_words(contract.parent_fee),
            'абонентская_плата': f"{contract.subscription_fee:.2f}",
            'питание': f"{contract.food_fee:.2f}",
            
            # Реквизиты учреждения
            'учреждение_название': 'Муниципальное бюджетное дошкольное образовательное учреждение Карабашский детский сад общеразвивающего вида №1 «Рябинушка» Бугульминского муниципального района Республики Татарстан',
            'учреждение_адрес': '423229, Республика Татарстан, Бугульминский район, пгт. Карабаш, ул. Октябрьская, д.6',
            'учреждение_телефон': '8(85594)5-06-85',
            'учреждение_инн': '1645012810',
            'учреждение_кпп': '164501001',
            'учреждение_бик': '049205001',
            'учреждение_рс': '40701810792053000013',
            'учреждение_лс': 'ЛБГ 13800095',
            'заведующая_физ': 'Михайлова Надежда Васильевна',
        }
        
        return context
    
    def _fill_document(self, doc, context):
        """Заполнение документа данными по плейсхолдерам"""
        
        # Заменяем в параграфах
        for paragraph in doc.paragraphs:
            self._replace_in_paragraph(paragraph, context)
        
        # Заменяем в таблицах
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        self._replace_in_paragraph(paragraph, context)
    
    def _replace_in_paragraph(self, paragraph, context):
        """Замена плейсхолдеров в параграфе"""
        original_text = paragraph.text
        
        # Проверяем наличие плейсхолдеров
        if '{{' not in original_text or '}}' not in original_text:
            return
        
        new_text = original_text
        for key, value in context.items():
            placeholder = f'{{{{{key}}}}}'
            new_text = new_text.replace(placeholder, str(value))
        
        if new_text != original_text:
            # Сохраняем выравнивание
            alignment = paragraph.alignment
            # Очищаем параграф
            paragraph.clear()
            # Добавляем новый текст
            run = paragraph.add_run(new_text)
            run.font.name = 'Times New Roman'
            run.font.size = Pt(12)
            if alignment:
                paragraph.alignment = alignment