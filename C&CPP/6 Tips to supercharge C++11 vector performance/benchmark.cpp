#include "stdafx.h"
#include "StopWatch.h"
#include <iostream>
#include <vector>
#include <list>
using namespace std;
struct BigTestStruct
{
  int iValue = 1;
  float fValue;
  long lValue;
  double dValue;
  char cNameArr[10];
  int iValArr[100];
};
struct TestRunAggregater
{
  double test1;
  double test2;
  double test3;
  void Reset()
  {
    test1 = test2 = test3 = 0;
  }
};
void FillVector(vector<BigTestStruct>& testVector);
int main()
{
  StopWatch sw;
  TestRunAggregater tg;
  tg.test1 = 0;
  tg.test2 = 0;
  tg.test3 = 0;
  // #1: Avoid unnecessary reallocate and copy cycles by reserving the size of vector ahead of time.
  vector<BigTestStruct> testVector1;
  vector<BigTestStruct> testVector2;
  for (int i = 0; i < 100; i++)
  {
    sw.Restart();
    FillVector(testVector1);
    tg.test1 += sw.ElapsedUs();
    sw.Restart();
    testVector2.reserve(10000);
    FillVector(testVector2);
    tg.test2 += sw.ElapsedUs();
    testVector1.clear();
    testVector1.shrink_to_fit();
    testVector2.clear();
    testVector2.shrink_to_fit();
  }
  cout << "Average Time to Fill Vector Without Reservation:" << (tg.test1 / 100) << endl;
  cout << "Average Time to Fill Vector With Reservation:" << (tg.test2 / 100) << endl;
  tg.Reset();
  // #2 Use shrink_to_fit() to release memory consumed by the vector – clear() or erase() does not release memory
  FillVector(testVector1);
  size_t capacity = testVector1.capacity();
  cout << "Capacity Before Erasing Elements:" << capacity << endl;
  testVector1.erase(testVector1.begin(), testVector1.begin() + 3); //
  capacity = testVector1.capacity();
  cout << "Capacity After Erasing 3 elements Elements:" << capacity << endl;
  testVector1.clear();
  capacity = testVector1.capacity();
  cout << "Capacity After clearing all emements:" << capacity << endl;
  testVector1.shrink_to_fit();
  capacity = testVector1.capacity();
  cout << "Capacity After shrinking the Vector:" << capacity << endl;
  // Point # 3: When filling up or copying into a vector, prefer assignment over insert() or push_back().
  cout << "Begining Test for Vector element enumeration " << endl;
  //Using an iterator
  vector<BigTestStruct> testVectorSum;
  FillVector(testVectorSum);
  for (int i = 0; i < 100; i++)
  {
    sw.Restart();
    int sum = 0;
    for (auto it = testVectorSum.begin(); it != testVectorSum.end(); ++it)
    {
      sum = sum + it->iValue;
    }
    tg.test1 += sw.ElapsedUs();
    //Using the at() member function
    sw.Restart();
    sum = 0;
    for (unsigned i = 0; i < testVectorSum.size(); ++i)
    {
      sum = sum + testVectorSum.at(i).iValue;
    }
    tg.test2 += sw.ElapsedUs();
    // Using the subscript notation
    sw.Restart();
    sum = 0;
    for (unsigned i = 0; i < testVectorSum.size(); ++i)
    {
      sum = sum + testVectorSum[i].iValue;
    }
    tg.test3 += sw.ElapsedUs();
  }
  cout << "Using Iterator:" << (tg.test1 / 100) << endl;
  cout << "Using at() :" << (tg.test2 / 100) << endl;
  cout << "Using subscripting:" << (tg.test3 / 100) << endl;
  tg.Reset();
  // Point # 4:  While iterating through elements in a std::vector, avoid the std::vector::at() function
  vector<BigTestStruct> sourceVector, destinationVector;
  FillVector(sourceVector);
  for (int i = 0; i < 100; i++)
  {
    // Assign sourceVector to destination vector
    sw.Restart();
    destinationVector = sourceVector;
    tg.test1 += sw.ElapsedUs();
    //Using std::vector::insert()
    vector<BigTestStruct> sourceVector1, destinationVector1;
    FillVector(sourceVector1);
    sw.Restart();
    destinationVector1.insert(destinationVector1.end(),
      sourceVector1.begin(),
      sourceVector1.end());
    tg.test2 += sw.ElapsedUs();
    //Using push_back()
    vector<BigTestStruct> sourceVector2, destinationVector2;
    FillVector(sourceVector2);
    sw.Restart();
    for (unsigned i = 0; i < sourceVector2.size(); ++i)
    {
      destinationVector2.push_back(sourceVector2[i]);
    }
    tg.test3 += sw.ElapsedUs();
  }
  cout << "Average of Assigning Vector :" << (tg.test1 / 100) << endl;
  cout << "Average of Using insert() :" << (tg.test2 / 100) << endl;
  cout << "Average of Using push_back :" << (tg.test3 / 100) << endl;
  tg.Reset();
  //Point # 5:  Don’t use push-front() – its O(n) - if for some reason you need to use push_front(), consider using a std::list
  vector<BigTestStruct> sourceVector3, pushFrontTestVector;
  FillVector(sourceVector3);
  list<BigTestStruct> pushFrontTestList;
  for (int i = 0; i < 100; i++)
  {
    //Push 100k elements in front of the new vector -- this is horrible code !!!
    sw.Restart();
    for (unsigned i = 1; i < sourceVector3.size(); ++i)
    {
      pushFrontTestVector.insert(pushFrontTestVector.begin(), sourceVector3[i]);
    }
    tg.test1 += sw.ElapsedUs();
    // push in front of a list
    sw.Restart();
    for (unsigned i = 0; i < sourceVector3.size(); ++i)
    {
      pushFrontTestList.push_front(sourceVector3[i]);
    }
    tg.test2 += sw.ElapsedUs();
  }
  cout << "Average of Pushing in front of Vector :" << (tg.test1 / 100) << endl;
  cout << "Average of Pushing in front of list :" << (tg.test2 / 100) << endl;
  tg.Reset();
  // Point # 6: Prefer emplace_back() instead of push_back() while inserting into a vector
  vector<BigTestStruct> sourceVector4, pushBackTestVector, emplaceBackTestVector;
  FillVector(sourceVector4);
  for (int i = 0; i < 100; i++)
  {
    //Test push back performance
    sw.Restart();
    for (unsigned i = 0; i < sourceVector4.size(); ++i)
    {
      pushBackTestVector.push_back(sourceVector4[i]);
    }
    tg.test1 += sw.ElapsedUs();
    //Test emplace_back()
    sw.Restart();
    for (unsigned i = 0; i < sourceVector4.size(); ++i)
    {
      emplaceBackTestVector.emplace_back(sourceVector4[i]);
    }
    tg.test2 += sw.ElapsedUs();
  }
  cout << "Average Using push_back :" << (tg.test1 / 100) << endl;
  cout << "Average Using emplace_back :" << (tg.test2 / 100) << endl;
  return 0;
}
// Fuctions to show the benefit of vector::reserve()
void FillVector(vector<BigTestStruct>& testVector)
{
  for (int i = 0; i < 10000; i++)
  {
    BigTestStruct bt;
    testVector.push_back(bt);
  }
}