// Chakra Imports
import {
  Drawer,
  DrawerBody,
  DrawerCloseButton,
  DrawerContent,
  DrawerHeader,
} from '@chakra-ui/modal';
import { useDisclosure } from '@chakra-ui/hooks';
import React from 'react';
import Light from '/public/img/layout/Light.png';
import Dark from '/public/img/layout/Dark.png';
import DefaultSidebar from '/public/img/layout/DefaultSidebar.png';
import DefaultSidebarDark from '/public/img/layout/DefaultSidebarDark.png';
import MiniSidebar from '/public/img/layout/MiniSidebar.png';
import MiniSidebarDark from '/public/img/layout/MiniSidebarDark.png';
import ConfiguratorLogo from '/public/img/layout/ConfiguratorLogo.png';
import Image from 'next/image';
// Assets
import { MdSettings } from 'react-icons/md';
import ConfiguratorRadio from './ConfiguratorRadio';

// 精简版 Configurator：仅保留外观（亮/暗）与侧边栏（默认/最小化）。
// props 接口保持不变（mini/setMini/theme/setTheme/darkmode/setDarkmode），
// theme/setTheme 不再使用但仍接收，故经由 props.* 访问以避免 eslint 未使用变量告警。
export default function HeaderLinks(props: { [x: string]: any }) {
  const { darkmode, setDarkmode } = props;
  //eslint-disable-next-line
  const { isOpen, onOpen, onClose } = useDisclosure();
  const btnRef = React.useRef();
  return (
    <>
      <button
        ref={btnRef}
        className="h-[18px] min-h-[unset] w-max min-w-[unset] bg-none p-0"
        onClick={onOpen}
      >
        <MdSettings className="h-[18px] w-[18px] text-gray-400 dark:text-white" />
      </button>
      <Drawer
        isOpen={isOpen}
        onClose={onClose}
        placement={document.documentElement.dir === 'rtl' ? 'left' : 'right'}
      >
        <DrawerContent className="my-4 ml-0 mr-4 w-[calc(100vw_-_32px)] max-w-[calc(100vw_-_32px)] rounded-2xl bg-white shadow-[-20px_17px_40px_4px_rgba(112,_144,_176,_0.18)] dark:bg-navy-800 dark:shadow-[-22px_32px_51px_4px_#0B1437] sm:ml-4 md:w-[400px] md:max-w-[400px]">
          <DrawerHeader
            px="28px"
            w={{ base: '100%', md: '400px' }}
            pt="24px"
            pb="0px"
          >
            <DrawerCloseButton className="absolute right-[26px] top-[16px] h-4 w-4 text-gray-900 dark:text-white" />
            <div className="flex items-center">
              <div className="relative mr-5 flex h-12 w-12 rounded-full bg-gradient-to-b from-brand-400 to-brand-600">
                <Image
                  fill
                  style={{ objectFit: 'contain' }}
                  alt=""
                  src={ConfiguratorLogo}
                />
              </div>
              <div>
                <p className="text-xl font-bold text-gray-900 dark:text-white">
                  Configurator
                </p>
                <p className="text-md flex font-medium text-gray-600">
                  Invoce 外观
                </p>
              </div>
            </div>
            <div className="my-[30px] h-px w-full bg-gray-200 dark:!bg-navy-700" />
          </DrawerHeader>
          <DrawerBody
            overflowY="scroll"
            px="28px"
            pt="0px"
            pb="24px"
            w={{ base: '100%', md: '400px' }}
            maxW="unset"
          >
            <div className="flex flex-col">
              <p className="mb-3 font-bold text-gray-900 dark:text-white">
                Color Mode
              </p>
              <div className="mb-7 flex w-full justify-between gap-5">
                <ConfiguratorRadio
                  onClick={() => {
                    if (darkmode) {
                      document.body.classList.remove('dark');
                      setDarkmode(false);
                    }
                  }}
                  active={
                    document.body.classList.contains('dark') ? false : true
                  }
                  label={
                    <p className="font-bold text-gray-900 dark:text-white">
                      Light
                    </p>
                  }
                >
                  <div className="relative h-[70px] w-full">
                    <Image
                      fill
                      style={{ objectFit: 'contain' }}
                      className="max-w-[130px] rounded-lg"
                      src={Light}
                      alt="avatar"
                    />
                  </div>
                </ConfiguratorRadio>
                <ConfiguratorRadio
                  onClick={() => {
                    if (!darkmode) {
                      document.body.classList.add('dark');
                      setDarkmode(true);
                    }
                  }}
                  active={
                    !document.body.classList.contains('dark') ? false : true
                  }
                  label={
                    <p className="font-bold text-gray-900 dark:text-white">
                      Dark
                    </p>
                  }
                >
                  <div className="relative h-[70px] w-full">
                    <Image
                      fill
                      style={{ objectFit: 'contain' }}
                      className="max-w-[130px] rounded-lg"
                      alt=""
                      src={Dark}
                    />
                  </div>
                </ConfiguratorRadio>
              </div>
              <p className="mb-3 font-bold text-gray-900 dark:text-white">
                Sidebar
              </p>
              <div className="mb-7 flex w-full justify-between gap-5">
                <ConfiguratorRadio
                  onClick={() => props.setMini(false)}
                  active={props.mini === true ? false : true}
                  label={
                    <p className="font-bold text-gray-900 dark:text-white">
                      Default
                    </p>
                  }
                >
                  <div
                    className={`relative flex min-h-[126px] w-[130px] items-center justify-center overflow-hidden rounded-[10px] border-[1px] border-gray-200 bg-gray-100 bg-repeat pl-2.5 pt-2.5 dark:border-[#323B5D] dark:bg-navy-900`}
                  >
                    <Image
                      fill
                      style={{ objectFit: 'contain' }}
                      className="mx-auto my-auto max-h-[70px] max-w-full rounded-md shadow-[0px_6px_14px_rgba(200,_207,_215,_0.6)] dark:shadow-none md:max-w-[96px]"
                      alt=""
                      src={
                        document.body.classList.contains('dark')
                          ? DefaultSidebarDark
                          : DefaultSidebar
                      }
                    />
                  </div>
                </ConfiguratorRadio>
                <ConfiguratorRadio
                  onClick={() => props.setMini(true)}
                  active={props.mini === false ? false : true}
                  label={
                    <p className="font-bold text-gray-900 dark:text-white">
                      Minimized
                    </p>
                  }
                >
                  <div
                    className={`relative flex min-h-[126px] w-[130px] items-center justify-center overflow-hidden rounded-[10px] border-[1px] border-gray-200 bg-gray-100 bg-repeat pl-2.5 pt-2.5 dark:border-[#323B5D] dark:bg-navy-900`}
                  >
                    <Image
                      fill
                      style={{ objectFit: 'contain' }}
                      className="mx-auto my-auto max-h-[70px] max-w-full rounded-md shadow-[0px_6px_14px_rgba(200,_207,_215,_0.6)] dark:shadow-none md:max-w-[75px]"
                      alt=""
                      src={
                        document.body.classList.contains('dark')
                          ? MiniSidebarDark
                          : MiniSidebar
                      }
                    />
                  </div>
                </ConfiguratorRadio>
              </div>
            </div>
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </>
  );
}
