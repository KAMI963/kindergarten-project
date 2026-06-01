from django import forms
from .models import ChildApplication, ApplicationStatus, BenefitCategory, AgeCategory
from datetime import date, timedelta
from children.models import Group, Child


class ChildApplicationForm(forms.ModelForm):
    """Форма создания/редактирования заявления"""
    
    # Поле для группы крови с выбором из списка
    BLOOD_TYPE_CHOICES = [
        ('', '---------'),
        ('I+', 'I (0) Rh+'),
        ('I-', 'I (0) Rh-'),
        ('II+', 'II (A) Rh+'),
        ('II-', 'II (A) Rh-'),
        ('III+', 'III (B) Rh+'),
        ('III-', 'III (B) Rh-'),
        ('IV+', 'IV (AB) Rh+'),
        ('IV-', 'IV (AB) Rh-'),
    ]
    
    blood_type = forms.ChoiceField(
        choices=BLOOD_TYPE_CHOICES,
        required=False,
        label='Группа крови и резус-фактор'
    )
    
    # Поле для предпочтительной группы с выбором из существующих групп
    preferred_group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=False,
        empty_label="Не выбрано",
        label='Предпочтительная группа'
    )
    
    # Поле для льготы - используем обновленный BenefitCategory.choices
    benefit_category = forms.ChoiceField(
        choices=BenefitCategory.choices,
        required=False,
        label='Категория льготы',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'benefit_category'})
    )
    
    # Дополнительные чекбоксы для отображения
    is_foreign_citizen = forms.BooleanField(
        required=False,
        label='Иностранный гражданин',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    is_guardianship = forms.BooleanField(
        required=False,
        label='Опекунство',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    require_health_group = forms.BooleanField(
        required=False,
        label='Требуется оздоровительная группа',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    require_compensating_group = forms.BooleanField(
        required=False,
        label='Требуется компенсирующая группа',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    # Поле для выбора брата/сестры
    sibling_child_id = forms.ChoiceField(
        required=False,
        label='Брат/сестра, который уже посещает детский сад',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'sibling_child_select'})
    )
    
    class Meta:
        model = ChildApplication
        fields = [
            # ===== ДАННЫЕ РЕБЕНКА =====
            'child_full_name', 'child_birth_date', 'child_gender', 'child_snils',
            'child_photo',
            
            # ===== ДОКУМЕНТЫ РЕБЕНКА =====
            'child_snils_file',
            'vaccination_certificate_file',
            'insurance_policy_file',
            'medical_card_a4_file',
            
            # ===== СВИДЕТЕЛЬСТВО О РОЖДЕНИИ =====
            'birth_certificate_series', 'birth_certificate_number',
            'birth_certificate_issue_date', 'birth_certificate_issued_by',
            'birth_certificate_file', 'birth_certificate_translation',
            
            # ===== АДРЕСНЫЕ ДАННЫЕ =====
            'registration_address', 'actual_address',
            'residence_certificate',
            
            # ===== КОНТАКТНЫЕ ДАННЫЕ =====
            'phone_number', 'email',
            
            # ===== ДАННЫЕ ЗАЯВИТЕЛЕЙ =====
            'applicant1_full_name', 'applicant1_phone', 'applicant1_is_primary',
            'applicant1_passport_file',
            'applicant2_full_name', 'applicant2_phone',
            'applicant2_passport_file',
            
            # ===== МЕДИЦИНСКИЕ ДАННЫЕ =====
            'has_vaccinations', 'chronic_diseases', 'medical_notes',
            'blood_type', 'allergies', 'special_needs',
            'medical_card',
            'health_certificate_oz', 'pmpk_conclusion',
            
            # ===== ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ =====
            'preferred_group', 'enrollment_date', 'additional_info',
            
            # ===== ДОКУМЕНТЫ =====
            'additional_documents',
            'health_certificate',
            'pmpk_file',
            'foreign_documents',
            'guardianship_act',
            'guardianship_act_doc',
            'foreign_residence_doc',
            'benefit_document_right',
            
            # ===== ЛЬГОТЫ =====
            'benefit_category',
            'benefit_document',
            'sibling_in_kindergarten',
            
            # ===== СОГЛАСИЯ =====
            'data_processing_consent', 'rules_acquainted',
            'medical_examination_consent', 'photo_video_consent',
            
            # ===== ДОПОЛНИТЕЛЬНЫЕ ПОЛЯ =====
            'is_foreign_citizen', 'is_guardianship',
            'require_health_group', 'require_compensating_group',
        ]
        
        widgets = {
            # ===== ДАТЫ =====
            'child_birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'required': 'required'}),
            'birth_certificate_issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'enrollment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            
            # ===== ФОТО РЕБЕНКА =====
            'child_photo': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            
            # ===== ДОКУМЕНТЫ РЕБЕНКА =====
            'child_snils_file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg'
            }),
            'vaccination_certificate_file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg'
            }),
            'insurance_policy_file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg'
            }),
            'medical_card_a4_file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg'
            }),
            
            # ===== ТЕКСТОВЫЕ ПОЛЯ =====
            'child_full_name': forms.TextInput(attrs={
                'class': 'form-control text-capitalize',
                'placeholder': 'Иванов Иван Иванович',
                'required': 'required'
            }),
            'child_snils': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '123-456-789 01',
            }),
            
            # ===== ЗАЯВИТЕЛЬ 1 (ОСНОВНОЙ) =====
            'applicant1_full_name': forms.TextInput(attrs={
                'class': 'form-control text-capitalize',
                'required': 'required'
            }),
            'applicant1_phone': forms.TextInput(attrs={
                'class': 'form-control phone-mask',
                'placeholder': '+7 (999) 999-99-99'
            }),
            'applicant1_is_primary': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'applicant1_passport_file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg',
                'required': 'required'
            }),
            
            # ===== ЗАЯВИТЕЛЬ 2 =====
            'applicant2_full_name': forms.TextInput(attrs={
                'class': 'form-control text-capitalize'
            }),
            'applicant2_phone': forms.TextInput(attrs={
                'class': 'form-control phone-mask',
                'placeholder': '+7 (999) 999-99-99'
            }),
            'applicant2_passport_file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg'
            }),
            
            # ===== КОНТАКТЫ =====
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control phone-mask',
                'placeholder': '+7 (999) 999-99-99',
                'required': 'required'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'example@mail.ru'
            }),
            
            # ===== СВИДЕТЕЛЬСТВО О РОЖДЕНИИ =====
            'birth_certificate_series': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'IV-АМ',
            }),
            'birth_certificate_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '123456',
            }),
            'birth_certificate_issued_by': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Отдел ЗАГС по...'
            }),
            'birth_certificate_file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg',
                'required': 'required'
            }),
            'birth_certificate_translation': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg'
            }),
            
            # ===== АДРЕСА =====
            'registration_address': forms.Textarea(attrs={
                'rows': 2, 
                'class': 'form-control address-input',
                'required': 'required',
                'placeholder': 'г. Москва, ул. Примерная, д. 1, кв. 1'
            }),
            'actual_address': forms.Textarea(attrs={
                'rows': 2, 
                'class': 'form-control address-input',
                'placeholder': 'г. Москва, ул. Примерная, д. 1, кв. 1'
            }),
            'residence_certificate': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg',
                'required': 'required'
            }),
            
            # ===== МЕДИЦИНСКИЕ ДАННЫЕ =====
            'chronic_diseases': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'medical_notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'allergies': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'special_needs': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'additional_info': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'medical_card': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg',
                'required': 'required'
            }),
            'health_certificate_oz': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg'
            }),
            'pmpk_conclusion': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg'
            }),
            
            # ===== ДОПОЛНИТЕЛЬНЫЕ ДОКУМЕНТЫ =====
            'additional_documents': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg'
            }),
            'health_certificate': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg'
            }),
            'pmpk_file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg'
            }),
            'foreign_documents': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg'
            }),
            'foreign_residence_doc': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg'
            }),
            'guardianship_act': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg'
            }),
            'guardianship_act_doc': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg'
            }),
            'benefit_document': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg'
            }),
            'benefit_document_right': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.png,.jpeg'
            }),
            
            # ===== ЧЕКБОКСЫ =====
            'has_vaccinations': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sibling_in_kindergarten': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'sibling_checkbox'}),
            'data_processing_consent': forms.CheckboxInput(attrs={'class': 'form-check-input', 'required': 'required'}),
            'rules_acquainted': forms.CheckboxInput(attrs={'class': 'form-check-input', 'required': 'required'}),
            'medical_examination_consent': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'photo_video_consent': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'child_gender': forms.Select(attrs={'class': 'form-select', 'required': 'required'}),
        }
        
        labels = {
            # ===== ДАННЫЕ РЕБЕНКА =====
            'child_full_name': 'ФИО ребенка *',
            'child_birth_date': 'Дата рождения *',
            'child_gender': 'Пол *',
            'child_snils': 'СНИЛС ребенка (номер)',
            'child_photo': 'Фотография ребенка',
            
            # ===== ДОКУМЕНТЫ РЕБЕНКА =====
            'child_snils_file': 'СНИЛС ребенка (скан)',
            'vaccination_certificate_file': 'Сертификат о прививках (форма № 063/у)',
            'insurance_policy_file': 'Полис медицинского страхования',
            'medical_card_a4_file': 'Медицинская карта ребенка (форма № 026/у) А4',
            
            # ===== СВИДЕТЕЛЬСТВО О РОЖДЕНИИ =====
            'birth_certificate_series': 'Серия свидетельства о рождении',
            'birth_certificate_number': 'Номер свидетельства о рождении',
            'birth_certificate_issue_date': 'Дата выдачи свидетельства',
            'birth_certificate_issued_by': 'Кем выдано свидетельство',
            'birth_certificate_file': 'Свидетельство о рождении *',
            'birth_certificate_translation': 'Перевод свидетельства о рождении (нотариально заверенный)',
            
            # ===== АДРЕСА =====
            'registration_address': 'Адрес регистрации *',
            'actual_address': 'Фактический адрес проживания',
            'residence_certificate': 'Подтверждение места жительства *',
            
            # ===== КОНТАКТЫ =====
            'phone_number': 'Контактный телефон *',
            'email': 'Электронная почта',
            
            # ===== ЗАЯВИТЕЛИ =====
            'applicant1_full_name': 'ФИО заявителя (лицо, подписывающее документы) *',
            'applicant1_phone': 'Телефон заявителя',
            'applicant1_is_primary': 'Это основной заявитель',
            'applicant1_passport_file': 'Паспорт заявителя *',
            'applicant2_full_name': 'ФИО второго заявителя',
            'applicant2_phone': 'Телефон второго заявителя',
            'applicant2_passport_file': 'Паспорт второго заявителя',
            
            # ===== МЕДИЦИНСКИЕ ДАННЫЕ =====
            'has_vaccinations': 'Наличие прививок',
            'chronic_diseases': 'Хронические заболевания',
            'medical_notes': 'Медицинские примечания',
            'blood_type': 'Группа крови',
            'allergies': 'Аллергии',
            'special_needs': 'Особые потребности',
            'medical_card': 'Медицинская карта *',
            'health_certificate_oz': 'Медицинская справка (оздоровительная группа)',
            'pmpk_conclusion': 'Заключение ПМПК (компенсирующая группа)',
            
            # ===== ЛЬГОТЫ =====
            'benefit_category': 'Категория льготы',
            'benefit_document': 'Документ, подтверждающий льготу',
            'benefit_document_right': 'Документ о праве на льготу',
            'sibling_in_kindergarten': 'Брат/сестра уже посещает этот детский сад',
            
            # ===== СОГЛАСИЯ =====
            'data_processing_consent': 'Согласие на обработку персональных данных *',
            'rules_acquainted': 'Ознакомление с правилами *',
            'medical_examination_consent': 'Согласие на медицинский осмотр',
            'photo_video_consent': 'Согласие на фото/видеосъемку',
            
            # ===== ДОПОЛНИТЕЛЬНЫЕ ПОЛЯ =====
            'is_foreign_citizen': 'Иностранный гражданин',
            'is_guardianship': 'Опекунство',
            'require_health_group': 'Требуется оздоровительная группа',
            'require_compensating_group': 'Требуется компенсирующая группа',
        }
    
    def __init__(self, *args, **kwargs):
        # Извлекаем request из kwargs, если он передан
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Устанавливаем желаемую дату зачисления по умолчанию
        if not self.instance.pk and not self.data.get('enrollment_date'):
            self.fields['enrollment_date'].initial = date.today() + timedelta(days=14)
        
        # Делаем обязательные поля
        required_fields = [
            'child_full_name', 'child_birth_date', 'child_gender',
            'registration_address', 'phone_number',
            'birth_certificate_file', 'medical_card', 
            'applicant1_passport_file', 'residence_certificate',
            'data_processing_consent', 'rules_acquainted',
        ]
        
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
                if hasattr(self.fields[field_name].widget, 'attrs'):
                    self.fields[field_name].widget.attrs['required'] = 'required'
        
        # actual_address - НЕ обязательное поле
        if 'actual_address' in self.fields:
            self.fields['actual_address'].required = False
            if hasattr(self.fields['actual_address'].widget, 'attrs'):
                self.fields['actual_address'].widget.attrs.pop('required', None)
        
        # Настройка поля sibling_child_id - выбор братьев/сестер
        if self.request and self.request.user.is_authenticated:
            self._setup_sibling_choices()
        
        # Автозаполнение из профиля родителя
        if self.request and self.request.user.is_authenticated and not self.instance.pk:
            self._auto_fill_from_profile()
    
    def _setup_sibling_choices(self):
        """Настройка выбора братьев/сестер"""
        choices = [('', '---------')]
        
        if self.request and hasattr(self.request.user, 'parentprofile'):
            try:
                siblings = self.request.user.parentprofile.get_siblings_in_kindergarten()
                for sibling in siblings:
                    group_name = sibling.group.name if sibling.group else 'группа не назначена'
                    choices.append((str(sibling.id), f'{sibling.full_name} ({group_name})'))
            except Exception as e:
                print(f"ERROR getting siblings: {e}")
        
        self.fields['sibling_child_id'].choices = choices
        
        if self.instance and self.instance.sibling_child_id:
            self.fields['sibling_child_id'].initial = str(self.instance.sibling_child_id)
    
    def _auto_fill_from_profile(self):
        """Автоматическое заполнение из профиля родителя"""
        if not self.request:
            return
        
        user = self.request.user
        
        if hasattr(user, 'parentprofile'):
            profile = user.parentprofile
            
            # Адреса
            if profile.registration_address and profile.registration_address != 'Не указан':
                self.fields['registration_address'].initial = profile.registration_address
            if profile.actual_address and profile.actual_address != 'Не указан':
                self.fields['actual_address'].initial = profile.actual_address
            elif profile.registration_address:
                self.fields['actual_address'].initial = profile.registration_address
            
            # Контакты
            if profile.mobile_phone:
                self.fields['phone_number'].initial = profile.mobile_phone
                self.fields['applicant1_phone'].initial = profile.mobile_phone
            elif user.phone:
                self.fields['phone_number'].initial = user.phone
                self.fields['applicant1_phone'].initial = user.phone
            
            if user.email:
                self.fields['email'].initial = user.email
            
            # ФИО заявителя
            user_full_name = profile.full_name or user.get_full_name()
            if user_full_name:
                self.fields['applicant1_full_name'].initial = user_full_name
    
    def clean(self):
        """Общая валидация формы"""
        cleaned_data = super().clean()
        child_birth_date = cleaned_data.get('child_birth_date')
        
        # Проверка возраста ребенка
        if child_birth_date:
            today = date.today()
            age = today.year - child_birth_date.year
            month_diff = today.month - child_birth_date.month
            day_diff = today.day - child_birth_date.day
            
            if month_diff < 0 or (month_diff == 0 and day_diff < 0):
                age -= 1
            
            age_in_months = age * 12 + month_diff
            if day_diff < 0:
                age_in_months -= 1
            
            if age_in_months < 18:
                raise forms.ValidationError("Ребенок должен быть старше 1.5 лет для поступления в детский сад.")
            if age > 7:
                raise forms.ValidationError("Ребенок должен быть младше 7 лет для поступления в детский сад.")
        
        # Проверка обязательных согласий
        if not cleaned_data.get('data_processing_consent'):
            raise forms.ValidationError("Необходимо дать согласие на обработку персональных данных.")
        
        if not cleaned_data.get('rules_acquainted'):
            raise forms.ValidationError("Необходимо ознакомиться с правилами внутреннего распорядка.")
        
        # Если требуется оздоровительная группа, нужна справка
        if cleaned_data.get('require_health_group'):
            if not cleaned_data.get('health_certificate_oz') and not self.instance.health_certificate_oz:
                raise forms.ValidationError("Для оздоровительной группы необходима медицинская справка с рекомендацией врача.")
        
        # Если требуется компенсирующая группа, нужно заключение ПМПК
        if cleaned_data.get('require_compensating_group'):
            if not cleaned_data.get('pmpk_conclusion') and not self.instance.pmpk_conclusion:
                raise forms.ValidationError("Для компенсирующей группы необходимо заключение ПМПК.")
        
        # Если иностранный гражданин, нужны дополнительные документы
        if cleaned_data.get('is_foreign_citizen'):
            if not cleaned_data.get('foreign_residence_doc') and not self.instance.foreign_residence_doc:
                raise forms.ValidationError("Для иностранных граждан необходим документ о праве находиться в России.")
            if not cleaned_data.get('birth_certificate_translation') and not self.instance.birth_certificate_translation:
                raise forms.ValidationError("Для иностранных граждан необходим нотариально заверенный перевод свидетельства о рождении.")
        
        # Если опекунство, нужен акт
        if cleaned_data.get('is_guardianship'):
            if not cleaned_data.get('guardianship_act_doc') and not self.instance.guardianship_act_doc:
                raise forms.ValidationError("При опекунстве необходим акт о назначении опекуна.")
        
        # Если есть льгота (не none), нужен подтверждающий документ
        benefit = cleaned_data.get('benefit_category')
        if benefit and benefit != 'none':
            if not cleaned_data.get('benefit_document_right') and not cleaned_data.get('benefit_document'):
                if not self.instance.benefit_document_right and not self.instance.benefit_document:
                    raise forms.ValidationError("Для подтверждения льготы необходимо загрузить соответствующий документ.")
        
        # Если выбран брат/сестра, устанавливаем связь
        sibling_child_id = cleaned_data.get('sibling_child_id')
        if sibling_child_id and sibling_child_id != '':
            try:
                from children.models import Child
                sibling_child = Child.objects.get(id=int(sibling_child_id))
                cleaned_data['sibling_child'] = sibling_child
                cleaned_data['sibling_in_kindergarten'] = True
            except Child.DoesNotExist:
                pass
        
        return cleaned_data
    
    def clean_child_full_name(self):
        """Приведение ФИО к правильному формату"""
        full_name = self.cleaned_data.get('child_full_name', '')
        return ' '.join(word.capitalize() for word in full_name.split())
    
    def clean_applicant1_full_name(self):
        """Приведение ФИО заявителя к правильному формату"""
        full_name = self.cleaned_data.get('applicant1_full_name', '')
        return ' '.join(word.capitalize() for word in full_name.split()) if full_name else ''
    
    def clean_applicant2_full_name(self):
        """Приведение ФИО второго заявителя к правильному формату"""
        full_name = self.cleaned_data.get('applicant2_full_name', '')
        return ' '.join(word.capitalize() for word in full_name.split()) if full_name else ''
    
    def clean_child_snils(self):
        """Валидация СНИЛС"""
        snils = self.cleaned_data.get('child_snils', '')
        if snils:
            import re
            cleaned = re.sub(r'\D', '', snils)
            if len(cleaned) == 11:
                return f"{cleaned[:3]}-{cleaned[3:6]}-{cleaned[6:9]} {cleaned[9:11]}"
            elif len(cleaned) == 0:
                return ''
            else:
                raise forms.ValidationError("СНИЛС должен содержать 11 цифр")
        return snils
    
    def clean_applicant1_phone(self):
        """Очистка номера телефона заявителя"""
        phone = self.cleaned_data.get('applicant1_phone', '')
        return self._clean_phone_number(phone)
    
    def clean_applicant2_phone(self):
        """Очистка номера телефона второго заявителя"""
        phone = self.cleaned_data.get('applicant2_phone', '')
        return self._clean_phone_number(phone)
    
    def clean_phone_number(self):
        """Очистка основного номера телефона"""
        phone = self.cleaned_data.get('phone_number', '')
        if not phone:
            return ''
        return self._clean_phone_number(phone)
    
    def _clean_phone_number(self, phone):
        """Универсальная очистка номера телефона"""
        if phone:
            import re
            cleaned = re.sub(r'\D', '', phone)
            if cleaned.startswith('8') and len(cleaned) == 11:
                cleaned = '7' + cleaned[1:]
            elif len(cleaned) == 10:
                cleaned = '7' + cleaned
            if len(cleaned) == 11 and cleaned.startswith('7'):
                return f'+7({cleaned[1:4]}){cleaned[4:7]}-{cleaned[7:9]}-{cleaned[9:11]}'
        return phone
    
    def clean_birth_certificate_series(self):
        """Валидация серии свидетельства о рождении"""
        series = self.cleaned_data.get('birth_certificate_series', '')
        if series:
            import re
            series = series.upper().strip()
            pattern = r'^[IVXLCDM]+-[А-ЯЁ]{2}$'
            if not re.match(pattern, series):
                raise forms.ValidationError("Формат серии: римские цифры, дефис, 2 заглавные буквы (например: IV-АМ)")
        return series
    
    def clean_birth_certificate_number(self):
        """Валидация номера свидетельства о рождении"""
        number = self.cleaned_data.get('birth_certificate_number', '')
        if number:
            import re
            cleaned = re.sub(r'\D', '', number)
            if len(cleaned) != 6:
                raise forms.ValidationError("Номер свидетельства о рождении должен содержать 6 цифр")
            return cleaned
        return number
    
    def save(self, commit=True):
        """Сохранение формы с дополнительной логикой"""
        instance = super().save(commit=False)
        
        # Устанавливаем выбранного брата/сестру
        if hasattr(self, 'cleaned_data') and self.cleaned_data.get('sibling_child'):
            instance.sibling_child = self.cleaned_data['sibling_child']
            instance.sibling_in_kindergarten = True
        
        if commit:
            instance.save()
            self.save_m2m()
        
        return instance


class ApplicationVerificationForm(forms.Form):
    """Форма проверки документов"""
    documents_verified = forms.BooleanField(
        required=False,
        label='Документы проверены',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    verification_comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        label='Примечание проверяющего'
    )
    status = forms.ChoiceField(
        choices=[
            ('pending', 'На проверке'),
            ('queue', 'В очередь'),
            ('rejected', 'Отказать'),
            ('returned', 'Вернуть на доработку')
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Новый статус'
    )


class QueuePositionChangeForm(forms.Form):
    """Форма изменения позиции в очереди"""
    new_position = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='Новая позиция'
    )
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        label='Причина изменения'
    )


class EnrollmentOrderForm(forms.Form):
    """Форма создания приказа о зачислении"""
    order_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '2025-001'}),
        label='Номер приказа'
    )
    order_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Дата приказа',
        initial=date.today
    )
    group_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Младшая группа №1'}),
        label='Группа для зачисления'
    )